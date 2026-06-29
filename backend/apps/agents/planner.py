"""Planner agent — workflow orchestration with LLM planning and deterministic fallback."""

import json

from django.utils import timezone

from apps.agents.models import AgentExecution, AgentExecutionStatus
from apps.agents.planner_context import (
    build_planner_context,
    build_planner_prompt_variables,
    context_to_json,
)
from apps.agents.planner_provider import (
    PLANNER_PROMPT_NAME,
    PlannerProvider,
    extract_constraints_from_goal,
    tool_plan_to_planned_agents,
)
from apps.agents.repositories import AgentExecutionRepository
from apps.applications.repositories import ApplicationRepository, InterviewPlanRepository
from apps.memory.services import MemoryService
from apps.prompts.services import PromptService
from apps.resumes.repositories import ApplicationMaterialRepository, ResumeAnalysisRepository, ResumeRepository
from apps.users.repositories import UserPreferenceRepository
from apps.workflows.intent import (
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_CONVERSATIONAL,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    build_planned_agents,
    classify_workflow_intent,
)

PLANNER_AGENT_NAME = "planner"
REPLANNER_AGENT_NAME = "replanner"


class PlannerAgent:
    def __init__(
        self,
        preference_repo: UserPreferenceRepository | None = None,
        resume_repo: ResumeRepository | None = None,
        analysis_repo: ResumeAnalysisRepository | None = None,
        agent_repo: AgentExecutionRepository | None = None,
        memory_service: MemoryService | None = None,
        prompt_service: PromptService | None = None,
        provider: PlannerProvider | None = None,
    ):
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.resume_repo = resume_repo or ResumeRepository()
        self.analysis_repo = analysis_repo or ResumeAnalysisRepository()
        self.agent_repo = agent_repo or AgentExecutionRepository()
        self.memory_service = memory_service or MemoryService()
        self.prompt_service = prompt_service or PromptService()
        self.provider = provider or PlannerProvider()
        self.application_repo = ApplicationRepository()
        self.material_repo = ApplicationMaterialRepository()
        self.interview_plan_repo = InterviewPlanRepository()

    def build_context(
        self, user, goal: str, *, workflow_intent: str | None = None
    ) -> dict:
        return build_planner_context(
            user,
            goal,
            workflow_intent=workflow_intent,
            preference_repo=self.preference_repo,
            resume_repo=self.resume_repo,
            analysis_repo=self.analysis_repo,
            memory_service=self.memory_service,
            application_repo=self.application_repo,
            material_repo=self.material_repo,
            interview_plan_repo=self.interview_plan_repo,
        )

    def plan(
        self, user, workflow, goal: str, *, workflow_intent: str | None = None
    ) -> dict:
        started_at = timezone.now()
        resolved_intent = workflow_intent or classify_workflow_intent(goal)
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=PLANNER_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={"goal": goal, "workflow_intent": resolved_intent},
            started_at=started_at,
        )

        try:
            context = self.build_context(user, goal, workflow_intent=resolved_intent)
            plan_summary = self._generate_plan_summary(context)
            suggested_steps = self._suggest_steps(context)

            generation = self._generate_plan(context)
            planned_agents = generation.planned_agents or build_planned_agents(resolved_intent)
            if generation.reasoning_summary and not generation.used_fallback:
                reasoning_summary = generation.reasoning_summary
            else:
                reasoning_summary = self._generate_agentic_fallback_reasoning(
                    context,
                    generation.constraints,
                    generation.tool_plan,
                    planned_agents,
                )
            if generation.user_visible_plan:
                plan_summary = f"{generation.user_visible_plan} {plan_summary}"
            elif generation.tool_plan and resolved_intent == WORKFLOW_INTENT_JOB_DISCOVERY:
                tools = " → ".join(step.get("tool", "") for step in generation.tool_plan)
                plan_summary = f"{plan_summary} Selected tools: {tools}."

            completed_at = timezone.now()

            execution.status = AgentExecutionStatus.COMPLETED
            execution.input_data = {"goal": goal, "context": context_to_json(context)}
            execution.output_data = {
                "suggested_steps": suggested_steps,
                "planned_agents": planned_agents,
                "workflow_intent": generation.intent or resolved_intent,
                "constraints": generation.constraints,
                "tool_plan": generation.tool_plan,
                "success_criteria": generation.success_criteria,
                "user_visible_plan": generation.user_visible_plan,
                "requires_confirmation": generation.requires_confirmation,
                "used_fallback": generation.used_fallback,
                "model_name": generation.model_name,
            }
            execution.reasoning_summary = reasoning_summary
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "plan_summary": plan_summary,
                "suggested_steps": suggested_steps,
                "planned_agents": planned_agents,
                "workflow_intent": generation.intent or resolved_intent,
                "context": self._apply_constraints_to_context(context, generation.constraints),
                "constraints": generation.constraints,
                "tool_plan": generation.tool_plan,
                "success_criteria": generation.success_criteria,
                "user_visible_plan": generation.user_visible_plan,
                "requires_confirmation": generation.requires_confirmation,
                "used_fallback": generation.used_fallback,
                "model_name": generation.model_name,
            }
        except Exception as exc:
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = timezone.now()
            execution.save()
            raise

    def replan(
        self,
        user,
        workflow,
        goal: str,
        *,
        context: dict,
        last_tool_result: dict,
        pending_tools: list[dict] | None = None,
    ) -> dict:
        """Inspect the latest tool result and decide whether to continue, replan, or ask user."""
        started_at = timezone.now()
        workflow_result = workflow.result or {}
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=REPLANNER_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data=context_to_json(
                {
                    "goal": goal,
                    "last_tool_result": last_tool_result,
                    "pending_tools": pending_tools or [],
                }
            ),
            started_at=started_at,
        )

        try:
            recent_executions = list(
                workflow.agent_executions.exclude(agent_name=REPLANNER_AGENT_NAME)
                .order_by("-completed_at", "-started_at")[:5]
            )
            execution_summaries = [
                ex.reasoning_summary
                for ex in recent_executions
                if ex.reasoning_summary
            ]

            replan_context = {
                "goal": goal,
                "context": context,
                "constraints": workflow_result.get("constraints") or context.get("planner_constraints") or {},
                "workflow_result": workflow_result,
                "last_tool_key": last_tool_result.get("tool", ""),
                "last_tool_result": last_tool_result,
                "pending_tools": pending_tools or [],
            }

            base_rendered = self.prompt_service.render(
                PLANNER_PROMPT_NAME,
                build_planner_prompt_variables(context),
            )
            replan_prompt = (
                f"{base_rendered['rendered_text']}\n\n"
                "## Replan after tool execution\n\n"
                f"Goal: {goal}\n\n"
                f"Current tool plan:\n{json.dumps(workflow_result.get('tool_plan') or [], indent=2)}\n\n"
                f"Workflow result summary:\n{json.dumps({k: workflow_result.get(k) for k in ('discovered_count', 'evaluated_count', 'accepted_count', 'top_match_score', 'completed_agents') if k in workflow_result}, indent=2)}\n\n"
                f"Last tool result:\n{json.dumps(last_tool_result, indent=2)}\n\n"
                f"Pending tools:\n{json.dumps(pending_tools or [], indent=2)}\n\n"
                f"Recent agent runs:\n{chr(10).join(execution_summaries) or 'None'}\n\n"
                "Return ONLY valid JSON with keys: action (continue|insert_tools|skip_tool|ask_user|complete|fail_with_reason), "
                "reason, tools_to_insert (array of tool steps), message (optional user-facing text)."
            )
            replan = self.provider.replan(replan_prompt, replan_context)

            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "action": replan.action,
                "reason": replan.reason,
                "tools_to_insert": replan.tools_to_insert,
                "message": replan.message,
                "used_fallback": replan.used_fallback,
                "model_name": replan.model_name,
            }
            execution.reasoning_summary = replan.reason or f"Replan action: {replan.action}"
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "action": replan.action,
                "reason": replan.reason,
                "tools_to_insert": replan.tools_to_insert,
                "message": replan.message,
                "used_fallback": replan.used_fallback,
            }
        except Exception as exc:
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = timezone.now()
            execution.save()
            raise

    def _generate_plan(self, context: dict):
        rendered = self.prompt_service.render(
            PLANNER_PROMPT_NAME,
            build_planner_prompt_variables(context),
        )
        return self.provider.generate(rendered["rendered_text"], context)

    def _apply_constraints_to_context(self, context: dict, constraints: dict) -> dict:
        merged = dict(context)
        if constraints:
            merged["planner_constraints"] = constraints
            prefs = dict(merged.get("preferences") or {})
            if constraints.get("remote_preference"):
                prefs["remote_preference"] = constraints["remote_preference"]
            if constraints.get("role") and not prefs.get("target_roles"):
                prefs["target_roles"] = [constraints["role"]]
            if constraints.get("location") and constraints["location"] != "remote":
                if not prefs.get("target_locations"):
                    prefs["target_locations"] = [constraints["location"]]
            merged["preferences"] = prefs
        return merged

    def _generate_plan_summary(self, context: dict) -> str:
        goal = context.get("goal", "").strip()
        intent = context.get("workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY)
        roles = context.get("preferences", {}).get("target_roles", [])
        role_phrase = roles[0] if roles else "your target roles"
        resume = context.get("active_resume")

        parts = [f"Planning workflow for: {goal}"]
        constraints = extract_constraints_from_goal(goal)
        constraint_bits = [
            f"{key}: {value}"
            for key, value in constraints.items()
            if key != "requires_company_research" and value
        ]
        if constraint_bits:
            parts.append(f"Extracted constraints — {', '.join(constraint_bits)}.")

        if roles:
            parts.append(f"Aligned with target role: {role_phrase}.")
        if resume:
            parts.append(
                f"Using active resume ({resume['filename']}) "
                f"with health score {resume.get('health_score', '—')}."
            )
        else:
            parts.append("Resume not yet uploaded — profile completion recommended first.")

        intent_outcomes = {
            WORKFLOW_INTENT_TAILOR_RESUME: (
                "This is a resume-tailoring workflow — no job board search will run. "
                "After planning, select a matching role or paste a job description "
                "to generate a tailored resume."
            ),
            WORKFLOW_INTENT_COVER_LETTER: (
                "This is a cover-letter workflow — no job board search will run. "
                "After planning, pick an opportunity to generate a tailored cover letter."
            ),
            WORKFLOW_INTENT_INTERVIEW_PREP: (
                "This is an interview-prep workflow — no job board search will run. "
                "Interview prep runs automatically from your resume and goal when the "
                "request is general, or from a named company/application when you ask "
                "for role-specific prep."
            ),
            WORKFLOW_INTENT_APPLICATION_TRACKING: (
                "This is an application-tracking workflow — no job board search will run. "
                "Review your Applications board and pipeline status after planning."
            ),
            WORKFLOW_INTENT_CONVERSATIONAL: (
                "This is a conversational request — no agents will run automatically. "
                "Use the chat panel to explore capabilities or start a career action."
            ),
            WORKFLOW_INTENT_JOB_DISCOVERY: (
                "Job search runs automatically after planning to discover matching "
                "opportunities, then roles are evaluated for match score."
            ),
        }
        parts.append(
            intent_outcomes.get(intent, intent_outcomes[WORKFLOW_INTENT_CONVERSATIONAL])
        )
        return " ".join(parts)

    def _generate_agentic_fallback_reasoning(
        self,
        context: dict,
        constraints: dict,
        tool_plan: list[dict],
        planned_agents: list[str],
    ) -> str:
        """Actionable fallback trace with extracted constraints and selected tools."""
        parts: list[str] = []
        goal = context.get("goal", "").strip()
        merged_constraints = {
            **extract_constraints_from_goal(goal),
            **(constraints or {}),
        }
        constraint_bits = [
            f"{key}: {value}"
            for key, value in merged_constraints.items()
            if key != "requires_company_research" and value
        ]
        if constraint_bits:
            parts.append(f"Extracted constraints — {', '.join(constraint_bits)}.")

        if tool_plan:
            tools = " → ".join(step.get("tool", "") for step in tool_plan if step.get("tool"))
            if tools:
                parts.append(f"Selected tools: {tools}.")
            for step in tool_plan:
                tool = step.get("tool")
                reason = step.get("reason") or step.get("why")
                if tool and reason:
                    parts.append(f"{tool}: {reason}")
        else:
            parts.append(f"Will run: {' → '.join(planned_agents)}.")

        if merged_constraints.get("requires_company_research"):
            parts.append(
                "First I will score roles for basic fit, then research companies "
                "only for viable matches before final scoring."
            )

        prefs = context.get("preferences", {})
        roles = prefs.get("target_roles", [])
        if roles:
            parts.append(f"Targeting: {', '.join(roles[:3])}.")

        resume = context.get("active_resume")
        if resume:
            parts.append(f"Resume: {resume['filename']}.")
        else:
            parts.append("No active resume — profile completion recommended.")

        return " ".join(parts)

    def _generate_reasoning_summary(
        self,
        context: dict,
        suggested_steps: list[dict],
        planned_agents: list[str],
    ) -> str:
        """Actionable planner trace — distinct from the narrative plan_summary."""
        parts: list[str] = []
        prefs = context.get("preferences", {})
        roles = prefs.get("target_roles", [])
        locations = prefs.get("target_locations", [])
        if roles:
            parts.append(f"Targeting: {', '.join(roles[:3])}.")
        if locations:
            parts.append(f"Locations: {', '.join(locations[:3])}.")

        resume = context.get("active_resume")
        if resume:
            health = resume.get("health_score")
            health_phrase = f" (health {health})" if health is not None else ""
            parts.append(f"Resume: {resume['filename']}{health_phrase}.")
        else:
            parts.append("No active resume — profile completion recommended.")

        snippets = context.get("memory_snippets", [])
        if snippets:
            parts.append(f"Using {len(snippets)} memory snippet(s).")

        pipeline = context.get("pipeline_counts", {})
        pipeline_bits: list[str] = []
        for key, label in (
            ("applications", "applications"),
            ("materials", "materials"),
            ("interview_plans", "interview plans"),
        ):
            count = pipeline.get(key, 0)
            if count:
                pipeline_bits.append(f"{count} {label}")
        if pipeline_bits:
            parts.append(f"Pipeline context: {', '.join(pipeline_bits)}.")

        agent_phrase = " → ".join(planned_agents)
        parts.append(f"Will run: {agent_phrase}.")

        if suggested_steps:
            first = suggested_steps[0]
            title = first.get("title", "Next step")
            description = (first.get("description") or "").strip()
            if description:
                parts.append(f"First action: {title} — {description}")
            else:
                parts.append(f"First action: {title}.")

        return " ".join(parts)

    def _suggest_steps(self, context: dict) -> list[dict]:
        intent = context.get("workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY)
        steps: list[dict] = []
        prefs = context.get("preferences", {})

        if not prefs.get("target_roles"):
            steps.append({
                "key": "complete_profile",
                "title": "Complete your profile",
                "description": "Add target roles or upload a resume to infer them.",
            })
        if not context.get("active_resume"):
            steps.append({
                "key": "upload_resume",
                "title": "Upload resume",
                "description": "Provide your resume for tailored applications.",
            })

        if intent == WORKFLOW_INTENT_TAILOR_RESUME:
            steps.append({
                "key": "pick_opportunity",
                "title": "Select a role to tailor for",
                "description": (
                    "Choose from saved or high-match opportunities, or paste "
                    "a job description directly in the workspace."
                ),
                "phase": 6,
            })
            steps.append({
                "key": "tailor_materials",
                "title": "Generate tailored resume",
                "description": (
                    "CareerPilot tailors your active resume to the role requirements "
                    "without inventing experience."
                ),
                "phase": 6,
            })
            return steps

        if intent == WORKFLOW_INTENT_COVER_LETTER:
            steps.append({
                "key": "pick_opportunity",
                "title": "Pick an opportunity",
                "description": (
                    "Choose a saved or high-match opportunity for your cover letter."
                ),
                "phase": 6,
            })
            steps.append({
                "key": "tailor_materials",
                "title": "Generate cover letter",
                "description": (
                    "Run Cover Letter from the opportunity detail panel using your "
                    "profile and company research."
                ),
                "phase": 6,
            })
            return steps

        if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
            steps.append({
                "key": "prepare_interviews",
                "title": "Generate interview prep plan",
                "description": (
                    "Interview Prep creates tailored questions, system design topics, "
                    "talking points, and a day-by-day practice checklist."
                ),
                "phase": 7,
            })
            return steps

        if intent == WORKFLOW_INTENT_APPLICATION_TRACKING:
            steps.append({
                "key": "track_applications",
                "title": "Review application pipeline",
                "description": (
                    "Use the Applications Kanban board to track status, follow-ups, "
                    "and next actions."
                ),
                "phase": 7,
            })
            pipeline = context.get("pipeline_counts", {})
            if pipeline.get("applications", 0) > 0:
                steps.append({
                    "key": "review_decisions",
                    "title": "Prioritize next actions",
                    "description": (
                        "Run the Decision Agent to recommend which applications "
                        "deserve follow-up or interview prep."
                    ),
                    "phase": 8,
                })
            return steps

        steps.append({
            "key": "discover_opportunities",
            "title": "Discover opportunities",
            "description": "Job search providers scan LinkedIn, Indeed, and other boards.",
        })
        constraints = extract_constraints_from_goal(context.get("goal", ""))
        steps.append({
            "key": "evaluate_opportunities",
            "title": "Evaluate job matches",
            "description": (
                "CareerPilot scores discovered roles on role fit, skills, "
                "location, and salary before any company research."
            ),
            "phase": 5,
        })
        if constraints.get("requires_company_research"):
            steps.append({
                "key": "research_companies",
                "title": "Verify company stage",
                "description": (
                    "Research companies only for roles that passed the match threshold "
                    "to verify growth-stage startup signals."
                ),
                "phase": 5,
            })
            steps.append({
                "key": "evaluate_opportunities_final",
                "title": "Re-evaluate with company evidence",
                "description": (
                    "Re-score researched roles with company-stage evidence."
                ),
                "phase": 5,
            })
        else:
            steps.append({
                "key": "research_companies",
                "title": "Research target companies",
                "description": (
                    "Run on-demand company research from opportunity details "
                    "for roles you want to explore further."
                ),
                "phase": 5,
            })
        steps.append({
            "key": "tailor_materials",
            "title": "Tailor application materials",
            "description": (
                "Generate a tailored resume and cover letter for saved or "
                "high-match opportunities from the opportunity detail panel."
            ),
            "phase": 6,
        })
        steps.append({
            "key": "track_applications",
            "title": "Track applications",
            "description": (
                "Mark opportunities as applied to create application records "
                "and manage your pipeline on the Applications Kanban board."
            ),
            "phase": 7,
        })
        steps.append({
            "key": "prepare_interviews",
            "title": "Prepare for interviews",
            "description": (
                "Generate on-demand interview prep plans from saved or applied "
                "opportunities with tailored materials and company research."
            ),
            "phase": 7,
        })
        pipeline = context.get("pipeline_counts", {})
        if (
            pipeline.get("applications", 0) > 0
            or pipeline.get("materials", 0) > 0
            or pipeline.get("interview_plans", 0) > 0
        ):
            steps.append({
                "key": "review_decisions",
                "title": "Review decision recommendations",
                "description": (
                    "Generate a Decision Agent recommendation to prioritize next "
                    "actions across opportunities, applications, materials, and interviews."
                ),
                "phase": 8,
            })
        return steps


__all__ = [
    "PLANNER_AGENT_NAME",
    "REPLANNER_AGENT_NAME",
    "PlannerAgent",
    "tool_plan_to_planned_agents",
]
