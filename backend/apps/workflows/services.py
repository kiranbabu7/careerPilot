"""Workflow business logic."""

import hashlib
import json
import logging

from django.utils import timezone

from apps.agents.interview_prep import INTERVIEW_PREP_AGENT_NAME, InterviewPrepAgent
from apps.agents.job_evaluation import JobEvaluationAgent
from apps.agents.job_search import JobSearchAgent
from apps.agents.material_context import NoActiveResumeError
from apps.agents.planner import PLANNER_AGENT_NAME, PlannerAgent
from apps.agents.planner_provider import (
    build_default_tool_plan,
    extract_constraints_from_goal,
    tool_plan_to_planned_agents,
)
from apps.agents.resume_tailoring import RESUME_TAILOR_AGENT_NAME, ResumeTailorAgent
from apps.applications.models import ApplicationStage
from apps.applications.repositories import ApplicationRepository
from apps.applications.services import ApplicationActivityService
from apps.agents.serializers import AgentExecutionSerializer
from apps.jobs.evaluation import HIGH_MATCH_THRESHOLD
from apps.jobs.models import OpportunityStatus
from apps.jobs.repositories import JobRepository, OpportunityRepository
from apps.memory.services import ActivityService, MemoryService
from apps.resumes.serializers import ApplicationMaterialSerializer
from apps.workflows.intent import (
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    INTERVIEW_PREP_SCOPE_APPLICATION,
    build_intent_classification,
    build_planned_agents,
    classify_interview_prep_scope,
    classify_workflow_intent,
    is_resume_based_interview_prep,
)
from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus
from apps.workflows.repositories import WorkflowRepository
from apps.workflows.serializers import WorkflowExecutionSerializer
from apps.workflows.tailor_options import build_tailor_options
from apps.workflows.tasks import dispatch_rerun_job_search, dispatch_workflow
from apps.workflows.tool_registry import ToolResult, WorkflowToolRegistry
from apps.workflows.langgraph_rerun import LangGraphRerunRunner
from apps.workflows.langgraph_runner import LangGraphWorkflowRunner

logger = logging.getLogger(__name__)

RERUN_PIPELINE_AGENTS = frozenset(
    {"job_search", "job_evaluation", "company_research"}
)


class WorkflowService:
    def __init__(
        self,
        repo: WorkflowRepository | None = None,
        planner: PlannerAgent | None = None,
        job_search_agent: JobSearchAgent | None = None,
        evaluation_agent: JobEvaluationAgent | None = None,
        opportunity_repo: OpportunityRepository | None = None,
        job_repo: JobRepository | None = None,
        resume_tailor_agent: ResumeTailorAgent | None = None,
        interview_prep_agent: InterviewPrepAgent | None = None,
        application_repo: ApplicationRepository | None = None,
        application_activity_service: ApplicationActivityService | None = None,
        activity_service: ActivityService | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.repo = repo or WorkflowRepository()
        self.planner = planner or PlannerAgent()
        self.job_search_agent = job_search_agent or JobSearchAgent()
        self.evaluation_agent = evaluation_agent or JobEvaluationAgent()
        self.opportunity_repo = opportunity_repo or OpportunityRepository()
        self.job_repo = job_repo or JobRepository()
        self.resume_tailor_agent = resume_tailor_agent or ResumeTailorAgent()
        self.interview_prep_agent = interview_prep_agent or InterviewPrepAgent()
        self.application_repo = application_repo or ApplicationRepository()
        self.application_activity_service = (
            application_activity_service or ApplicationActivityService()
        )
        self.activity_service = activity_service or ActivityService()
        self.memory_service = memory_service or MemoryService()
        self._tool_registry: WorkflowToolRegistry | None = None

    def _get_tool_registry(self) -> WorkflowToolRegistry:
        if self._tool_registry is None:
            self._tool_registry = WorkflowToolRegistry(self)
        return self._tool_registry

    def _broaden_search_context(self, context: dict) -> dict:
        """Relax search constraints after empty results."""
        broadened = dict(context)
        prefs = dict(broadened.get("preferences") or {})
        roles = list(prefs.get("target_roles") or [])
        if roles:
            primary = roles[0]
            for suffix in (" engineer", " developer", " roles"):
                if primary.endswith(suffix):
                    prefs["target_roles"] = [primary[: -len(suffix)].strip() or primary]
                    break
        prefs["remote_preference"] = "flexible"
        broadened["preferences"] = prefs
        constraints = dict(broadened.get("planner_constraints") or {})
        constraints.pop("company_stage", None)
        constraints["requires_company_research"] = False
        broadened["planner_constraints"] = constraints
        return broadened

    def _sanitize_workflow_result(self, result: dict) -> dict:
        return json.loads(json.dumps(result, default=str))

    def _append_completed_agent(self, workflow: WorkflowExecution, agent_name: str) -> None:
        completed = list((workflow.result or {}).get("completed_agents") or [])
        if agent_name not in completed:
            completed.append(agent_name)
        workflow.result = self._sanitize_workflow_result({
            **(workflow.result or {}),
            "completed_agents": completed,
        })
        workflow.save(update_fields=["result", "updated_at"])

    def _planner_reasoning_summary(self, plan_result: dict) -> str:
        execution = plan_result.get("execution")
        if execution is None:
            return ""
        summary = getattr(execution, "reasoning_summary", None)
        return summary if isinstance(summary, str) else ""

    def _list_tailor_candidate_opportunities(self, user):
        """Evaluated opportunities for tailor selection, including rejected roles."""
        return self.opportunity_repo.list_for_user(
            user,
            include_rejected=True,
            include_low_match=True,
        )

    def _build_tailor_options_payload(self, user, goal: str) -> dict:
        opportunities = self._list_tailor_candidate_opportunities(user)
        return build_tailor_options(opportunities, goal)

    def _build_workflow_tailor_options_payload(
        self, user, workflow: WorkflowExecution, goal: str
    ) -> dict:
        """Tailor options scoped to this workflow's discovered/evaluated roles."""
        refinement = (workflow.context or {}).get("refinement") or {}
        threshold = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        opportunities = self.opportunity_repo.list_for_workflow_refinement(
            user,
            workflow,
            include_borderline=True,
            include_rejected=False,
            high_match_threshold=threshold,
        )
        return build_tailor_options(opportunities, goal)

    def _supports_tailor_resume(self, workflow: WorkflowExecution) -> bool:
        result = workflow.result or {}
        intent = result.get("workflow_intent") or classify_workflow_intent(
            workflow.goal or ""
        )
        if intent == WORKFLOW_INTENT_TAILOR_RESUME:
            return True
        return (
            intent == WORKFLOW_INTENT_JOB_DISCOVERY
            and bool(result.get("tailor_selection_pending"))
        )

    def enable_tailor_selection_from_chat(
        self, user, workflow: WorkflowExecution, *, goal: str | None = None
    ) -> dict:
        """Set tailor picker state from workflow discoveries after chat follow-up."""
        goal_text = goal or workflow.goal or ""
        tailor_options = self._build_workflow_tailor_options_payload(
            user, workflow, goal_text
        )
        result = dict(workflow.result or {})
        result["tailor_selection_pending"] = True
        result["tailor_options"] = tailor_options
        result["next_action"] = "Pick a role below to tailor your resume."
        workflow.result = result
        workflow.save(update_fields=["result", "updated_at"])
        return tailor_options

    def _summarize_existing_opportunities(self, user) -> dict:
        """Lightweight lookup of saved/high-match opportunities (no Apify search)."""
        opportunities = self.opportunity_repo.list_for_user(user)
        high_match = [
            opportunity
            for opportunity in opportunities
            if opportunity.match_score is not None
            and opportunity.match_score >= HIGH_MATCH_THRESHOLD
        ]
        saved = [
            opportunity
            for opportunity in opportunities
            if opportunity.status == OpportunityStatus.SAVED
        ]
        recommended = saved or high_match or opportunities
        return {
            "existing_opportunity_count": len(opportunities),
            "high_match_count": len(high_match),
            "saved_count": len(saved),
            "recommended_opportunity_ids": [
                str(opportunity.id) for opportunity in recommended[:5]
            ],
        }

    def _next_action_for_intent(self, intent: str, opportunity_summary: dict) -> str:
        count = opportunity_summary.get("existing_opportunity_count", 0)
        saved = opportunity_summary.get("saved_count", 0)
        high_match = opportunity_summary.get("high_match_count", 0)

        if intent == WORKFLOW_INTENT_TAILOR_RESUME:
            if saved or high_match:
                return "Select a saved or high-match role below to tailor your resume."
            if count:
                return "Select a role below or paste a job description to tailor your resume."
            return (
                "Paste a job description below, or run job discovery first to build "
                "a list of roles."
            )

        if intent == WORKFLOW_INTENT_COVER_LETTER:
            if saved or high_match:
                return (
                    "Pick an opportunity and generate a cover letter from the detail panel."
                )
            return (
                "Save or evaluate an opportunity first, then generate a cover letter on demand."
            )

        if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
            return (
                "Interview prep runs automatically after planning when possible."
            )

        if intent == WORKFLOW_INTENT_APPLICATION_TRACKING:
            return "Review and update your applications on the Applications Kanban board."

        return ""

    def _seed_welcome_chat_message(self, user, workflow: WorkflowExecution) -> None:
        from apps.workflows.chat_service import WorkflowChatService

        WorkflowChatService().seed_welcome_message(user, workflow)

    def _evaluate_discovered_opportunities(
        self, user, workflow, context: dict
    ) -> dict:
        """Evaluate unevaluated opportunities linked to this workflow's job search."""
        from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD, HIGH_MATCH_THRESHOLD
        from apps.workflows.tool_progress import (
            append_tool_progress_event,
            complete_tool_progress,
            start_tool_progress,
            update_tool_progress_label,
        )

        opportunities = [
            opportunity
            for opportunity in self.opportunity_repo.list_unevaluated_for_workflow(
                workflow
            )
            if opportunity.source_agent != "custom_jd"
        ]
        if not opportunities:
            return {
                "evaluated_count": 0,
                "accepted_count": 0,
                "borderline_count": 0,
                "rejected_count": 0,
                "top_match_score": 0,
                "evaluation_executions": [],
            }

        start_tool_progress(
            workflow,
            tool="job_evaluation",
            total=len(opportunities),
        )

        evaluated_so_far = 0
        summary_counts = {
            "accepted": 0,
            "borderline": 0,
            "rejected": 0,
            "top": 0,
        }

        def _on_progress(opportunity, outcome):
            nonlocal evaluated_so_far
            job = opportunity.job
            score = outcome["match_score"]
            summary_counts["top"] = max(summary_counts["top"], score)
            if score >= HIGH_MATCH_THRESHOLD:
                summary_counts["accepted"] += 1
            elif score >= BORDERLINE_MATCH_THRESHOLD:
                summary_counts["borderline"] += 1
            else:
                summary_counts["rejected"] += 1

            update_tool_progress_label(
                workflow,
                current_label=f"{job.title} at {job.company}",
            )
            evaluated_so_far += 1
            append_tool_progress_event(
                workflow,
                {
                    "kind": "job_evaluation",
                    "job_title": job.title,
                    "company": job.company,
                    "match_score": score,
                    "recommendation": outcome["evaluation"]["recommendation"],
                },
            )
            workflow.result = {
                **(workflow.result or {}),
                "evaluated_count": evaluated_so_far,
                "accepted_count": summary_counts["accepted"],
                "borderline_count": summary_counts["borderline"],
                "rejected_count": summary_counts["rejected"],
                "top_match_score": summary_counts["top"],
            }
            workflow.save(update_fields=["result", "updated_at"])

        try:
            batch = self.evaluation_agent.evaluate_batch(
                user,
                opportunities,
                workflow=workflow,
                context=context,
                on_progress=_on_progress,
            )
        finally:
            complete_tool_progress(workflow, tool="job_evaluation")

        execution_data = []
        if batch.get("execution") is not None:
            execution_data = [AgentExecutionSerializer(batch["execution"]).data]

        return {
            "evaluated_count": batch["evaluated_count"],
            "accepted_count": batch["accepted_count"],
            "borderline_count": batch["borderline_count"],
            "rejected_count": batch["rejected_count"],
            "top_match_score": batch["top_match_score"],
            "evaluation_executions": execution_data,
        }

    def list_executions(self, user):
        return self.repo.list_for_user(user)

    def get_execution(self, user, workflow_id):
        return self.repo.get_for_user(user, workflow_id)

    def _hydrate_discovery_counts(self, workflow: WorkflowExecution, result: dict) -> tuple[int, int, int]:
        """Fill discovery counts from linked opportunities when workflow.result is stale."""
        discovered = int(result.get("discovered_count") or 0)
        evaluated = int(result.get("evaluated_count") or 0)
        accepted = int(result.get("accepted_count") or 0)
        if discovered or evaluated or accepted:
            return discovered, evaluated, accepted

        opportunities = self.opportunity_repo.list_for_workflow(workflow)
        if not opportunities:
            return 0, 0, 0

        evaluated_ops = [opp for opp in opportunities if opp.match_score is not None]
        hydrated_discovered = len(opportunities)
        hydrated_evaluated = len(evaluated_ops) if evaluated_ops else len(opportunities)
        hydrated_accepted = sum(
            1 for opp in evaluated_ops if opp.match_score >= HIGH_MATCH_THRESHOLD
        )
        return hydrated_discovered, hydrated_evaluated, hydrated_accepted

    def _backfill_agentic_plan_fields(
        self, workflow: WorkflowExecution, result: dict
    ) -> dict:
        """Ensure tool_plan/constraints exist for older workflows and fallback runs."""
        goal = workflow.goal or ""
        workflow_intent = result.get("workflow_intent") or classify_workflow_intent(goal)
        constraints = result.get("constraints")
        if not isinstance(constraints, dict) or not constraints:
            constraints = extract_constraints_from_goal(goal)

        tool_plan = result.get("tool_plan")
        if not isinstance(tool_plan, list) or not tool_plan:
            tool_plan = build_default_tool_plan(workflow_intent, constraints)

        planned_agents = result.get("planned_agents")
        if not isinstance(planned_agents, list) or not planned_agents:
            planned_agents = tool_plan_to_planned_agents(tool_plan, workflow_intent)

        reasoning_summary = result.get("reasoning_summary")
        if not reasoning_summary:
            planner_exec = (
                workflow.agent_executions.filter(agent_name=PLANNER_AGENT_NAME)
                .order_by("-completed_at", "-started_at")
                .first()
            )
            reasoning_summary = (
                planner_exec.reasoning_summary if planner_exec else ""
            )

        backfilled = {
            **result,
            "workflow_intent": workflow_intent,
            "constraints": constraints,
            "tool_plan": tool_plan,
            "planned_agents": planned_agents,
        }
        if reasoning_summary and not backfilled.get("reasoning_summary"):
            backfilled["reasoning_summary"] = reasoning_summary
        if not backfilled.get("user_visible_plan") and isinstance(
            backfilled.get("plan_summary"), str
        ):
            backfilled["user_visible_plan"] = backfilled["plan_summary"]
        if not backfilled.get("success_criteria"):
            from apps.agents.planner_provider import default_success_criteria

            backfilled["success_criteria"] = default_success_criteria(
                workflow_intent, constraints
            )
        return backfilled

    def build_detail_response(self, workflow: WorkflowExecution) -> dict:
        result = self._backfill_agentic_plan_fields(workflow, workflow.result or {})
        context = workflow.context or {}
        executions = list(
            workflow.agent_executions.order_by("started_at", "created_at")
        )
        workflow_intent = result.get("workflow_intent") or context.get(
            "workflow_intent", classify_workflow_intent(workflow.goal or "")
        )
        planned_agents = (
            result.get("planned_agents")
            or context.get("planned_agents")
            or build_planned_agents(workflow_intent)
        )
        completed_agents = result.get("completed_agents") or []
        discovered_count, evaluated_count, accepted_count = self._hydrate_discovery_counts(
            workflow, result
        )
        return {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "agent_executions": AgentExecutionSerializer(executions, many=True).data,
            "workflow_intent": workflow_intent,
            "planned_agents": planned_agents,
            "completed_agents": completed_agents,
            "plan_summary": result.get("plan_summary", ""),
            "suggested_steps": result.get("suggested_steps", []),
            "next_action": result.get("next_action", ""),
            "existing_opportunity_count": result.get("existing_opportunity_count", 0),
            "high_match_count": result.get("high_match_count", 0),
            "saved_count": result.get("saved_count", 0),
            "recommended_opportunity_ids": result.get("recommended_opportunity_ids", []),
            "discovered_count": discovered_count,
            "provider_summary": result.get("provider_summary", {"providers": {}}),
            "job_search_summary": result.get("job_search_summary", ""),
            "evaluated_count": evaluated_count,
            "accepted_count": accepted_count,
            "borderline_count": result.get("borderline_count", 0),
            "rejected_count": result.get("rejected_count", 0),
            "top_match_score": result.get("top_match_score", 0),
            "tailor_options": result.get("tailor_options"),
            "tailor_selection_pending": result.get("tailor_selection_pending", False),
            "search_rerun_in_progress": result.get("search_rerun_in_progress", False),
            "selected_opportunity_id": result.get("selected_opportunity_id"),
            "tailored_material_id": result.get("tailored_material_id"),
            "cover_letter_material_id": result.get("cover_letter_material_id"),
            "interview_plan_id": result.get("interview_plan_id"),
            "interview_prep_target_source": result.get("interview_prep_target_source"),
            "tool_plan": result.get("tool_plan", []),
            "constraints": result.get("constraints", {}),
            "success_criteria": result.get("success_criteria", []),
            "user_visible_plan": result.get("user_visible_plan", ""),
            "plan_history": result.get("plan_history", []),
            "replan_events": result.get("replan_events", []),
            "tool_results": result.get("tool_results", []),
            "requires_confirmation": result.get("requires_confirmation", False),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "tool_progress": result.get("tool_progress"),
        }

    def get_tailor_options(self, user, workflow_id) -> dict | None:
        workflow = self.get_execution(user, workflow_id)
        if workflow is None:
            return None

        result = workflow.result or {}
        if not self._supports_tailor_resume(workflow):
            return {"detail": "Workflow is not ready for resume tailoring."}

        tailor_options = result.get("tailor_options")
        if not tailor_options:
            goal = workflow.goal or ""
            if (
                result.get("workflow_intent") or classify_workflow_intent(goal)
            ) == WORKFLOW_INTENT_JOB_DISCOVERY:
                tailor_options = self._build_workflow_tailor_options_payload(
                    user, workflow, goal
                )
            else:
                tailor_options = self._build_tailor_options_payload(user, goal)
        return {
            "workflow_id": str(workflow.id),
            "goal": workflow.goal,
            "tailor_options": tailor_options,
            "tailor_selection_pending": result.get("tailor_selection_pending", True),
            "selected_opportunity_id": result.get("selected_opportunity_id"),
            "tailored_material_id": result.get("tailored_material_id"),
        }

    def _create_opportunity_from_custom_jd(
        self,
        user,
        workflow,
        *,
        title: str,
        company: str,
        job_description: str,
    ):
        description_hash = hashlib.sha256(job_description.encode()).hexdigest()[:16]
        dedupe_raw = f"custom:{title.lower()}:{company.lower()}:{description_hash}"
        dedupe_key = hashlib.sha256(dedupe_raw.encode()).hexdigest()

        job = self.job_repo.get_by_dedupe_key(dedupe_key)
        if job is None:
            job = self.job_repo.create(
                source="custom",
                title=title,
                company=company,
                description=job_description,
                dedupe_key=dedupe_key,
            )

        opportunity, _created = self.opportunity_repo.get_or_create_for_user_job(
            user,
            job,
            workflow=workflow,
            defaults={
                "status": OpportunityStatus.SAVED,
                "source_agent": "custom_jd",
                "match_context": "Pasted job description for resume tailoring.",
            },
        )
        if opportunity.workflow_execution_id != workflow.id:
            opportunity.workflow_execution = workflow
            opportunity.save(update_fields=["workflow_execution", "updated_at"])
        return opportunity

    def _link_opportunity_to_workflow(
        self, opportunity, workflow: WorkflowExecution
    ):
        if opportunity.workflow_execution_id != workflow.id:
            opportunity.workflow_execution = workflow
            opportunity.save(update_fields=["workflow_execution", "updated_at"])

    def _create_general_prep_opportunity(self, user, workflow, goal: str):
        from apps.users.repositories import UserPreferenceRepository

        prefs, _ = UserPreferenceRepository().get_or_create_for_user(user)
        title = prefs.target_roles[0] if prefs.target_roles else "Interview preparation"
        description_parts = []
        if is_resume_based_interview_prep(goal):
            description_parts.append(
                "Focus: build a structured revision plan covering every skill, project, "
                "and experience listed on the user's active resume over the requested timeframe."
            )
        description_parts.extend([
            f"Interview preparation goal: {goal}",
            f"Career goals: {prefs.career_goals or 'Not specified'}",
            f"Target roles: {', '.join(prefs.target_roles) or 'Not specified'}",
            f"Skills: {', '.join(prefs.skills) or 'Not specified'}",
        ])
        return self._create_opportunity_from_custom_jd(
            user,
            workflow,
            title=title,
            company="General interview prep",
            job_description="\n".join(description_parts),
        )

    def _collect_prep_company_names(self, user) -> tuple[tuple[str, ...], tuple[str, ...]]:
        application_companies = tuple(
            dict.fromkeys(
                app.opportunity.job.company.strip()
                for app in self.application_repo.list_for_user(user)
                if app.opportunity.job.company.strip()
            )
        )
        opportunity_companies = tuple(
            dict.fromkeys(
                opportunity.job.company.strip()
                for opportunity in self.opportunity_repo.list_for_user(user)
                if opportunity.job.company.strip()
            )
        )
        return application_companies, opportunity_companies

    def _resolve_interview_prep_target(
        self, user, workflow: WorkflowExecution, goal: str
    ) -> tuple:
        application_companies, opportunity_companies = self._collect_prep_company_names(
            user
        )
        prep_scope = classify_interview_prep_scope(
            goal,
            application_companies=application_companies,
            opportunity_companies=opportunity_companies,
        )
        if prep_scope != INTERVIEW_PREP_SCOPE_APPLICATION:
            opportunity = self._create_general_prep_opportunity(user, workflow, goal)
            return opportunity, None, "general"

        stage_priority = {
            ApplicationStage.INTERVIEWING: 0,
            ApplicationStage.OFFER: 1,
            ApplicationStage.APPLIED: 2,
            ApplicationStage.DRAFT: 3,
        }
        applications = self.application_repo.list_for_user(user)
        eligible = [app for app in applications if app.stage in stage_priority]
        if eligible:
            eligible.sort(
                key=lambda app: (
                    stage_priority[app.stage],
                    -(app.opportunity.match_score or 0),
                )
            )
            application = eligible[0]
            opportunity = application.opportunity
            self._link_opportunity_to_workflow(opportunity, workflow)
            return opportunity, application, "application"

        summary = self._summarize_existing_opportunities(user)
        for opportunity_id in summary.get("recommended_opportunity_ids", []):
            opportunity = self.opportunity_repo.get_for_user(user, opportunity_id)
            if opportunity is None:
                continue
            application = self.application_repo.get_for_opportunity(
                user, opportunity.id
            )
            self._link_opportunity_to_workflow(opportunity, workflow)
            return opportunity, application, "opportunity"

        opportunity = self._create_general_prep_opportunity(user, workflow, goal)
        return opportunity, None, "general"

    def _execute_interview_prep_tool(
        self, user, workflow: WorkflowExecution, *, goal: str
    ) -> ToolResult:
        opportunity, application, target_source = self._resolve_interview_prep_target(
            user, workflow, goal
        )
        prep_result = self.interview_prep_agent.generate(
            user,
            opportunity,
            application=application,
            workflow=workflow,
        )
        self.application_activity_service.record_interview_prep_generated(
            user, prep_result["plan"], application=application
        )

        plan = prep_result["plan"]
        job = opportunity.job
        if target_source == "general":
            next_action = (
                "Resume-based interview prep plan ready. Review your roadmap to "
                "revise everything from your resume below."
                if is_resume_based_interview_prep(goal)
                else "General interview prep plan ready for your goal. Review your "
                "roadmap and practice questions below."
            )
        elif target_source == "opportunity":
            next_action = (
                f"Interview prep plan ready for {job.title} at {job.company} "
                "(from a saved opportunity). Review your roadmap and practice "
                "questions below."
            )
        else:
            next_action = (
                f"Interview prep plan ready for {job.title} at {job.company} "
                "(from your active application). Review your roadmap and practice "
                "questions below."
            )

        workflow.result = {
            **(workflow.result or {}),
            "selected_opportunity_id": str(opportunity.id),
            "interview_plan_id": str(plan.id),
            "interview_prep_target_source": target_source,
            "next_action": next_action,
            "reasoning_summary": prep_result["reasoning_summary"],
        }
        workflow.save(update_fields=["result", "updated_at"])

        return ToolResult(
            tool="interview_prep",
            success=True,
            summary=prep_result.get("reasoning_summary", "Interview prep complete."),
            data={
                "interview_plan_id": str(plan.id),
                "selected_opportunity_id": str(opportunity.id),
                "interview_prep_target_source": target_source,
                "next_action": next_action,
                "reasoning_summary": prep_result["reasoning_summary"],
            },
            execution=prep_result["execution"],
        )

    def run_interview_prep_follow_up(
        self,
        user,
        workflow: WorkflowExecution,
        *,
        goal: str,
    ) -> dict:
        """Run interview prep from workflow chat follow-up."""
        opportunity, application, target_source = self._resolve_interview_prep_target(
            user, workflow, goal
        )
        prep_result = self.interview_prep_agent.generate(
            user,
            opportunity,
            application=application,
            workflow=workflow,
        )
        self.application_activity_service.record_interview_prep_generated(
            user, prep_result["plan"], application=application
        )

        plan = prep_result["plan"]
        job = opportunity.job
        plan_id = str(plan.id)
        view_hint = (
            "Use View prep plan below to open your full roadmap and practice questions."
        )
        if target_source == "general":
            assistant_reply = f"{prep_result['reasoning_summary']} {view_hint}"
        else:
            assistant_reply = (
                f"Interview prep plan ready for {job.title} at {job.company}. "
                f"{prep_result['reasoning_summary']} {view_hint}"
            )
        next_action = (
            f"Interview prep plan ready for {job.title} at {job.company}. "
            "Open View prep plan to review your roadmap and questions."
        )

        result = dict(workflow.result or {})
        workflow.result = {
            **result,
            "selected_opportunity_id": str(opportunity.id),
            "interview_plan_id": plan_id,
            "interview_prep_target_source": target_source,
            "next_action": next_action,
        }
        workflow.save(update_fields=["result", "updated_at"])

        return {
            "summary": (
                f"Interview prep generated for {job.title} at {job.company}."
            ),
            "assistant_reply": assistant_reply,
            "payload": {
                "opportunity_id": str(opportunity.id),
                "application_id": str(application.id) if application else None,
                "interview_plan_id": str(plan.id),
                "interview_prep_target_source": target_source,
                "agent_execution": AgentExecutionSerializer(
                    prep_result["execution"]
                ).data,
            },
        }

    def tailor_resume(
        self,
        user,
        workflow_id,
        *,
        opportunity_id=None,
        job_description: str | None = None,
        title: str | None = None,
        company: str | None = None,
    ) -> dict | None:
        workflow = self.get_execution(user, workflow_id)
        if workflow is None:
            return None

        result = workflow.result or {}
        intent = result.get("workflow_intent") or classify_workflow_intent(
            workflow.goal or ""
        )
        if not self._supports_tailor_resume(workflow):
            return {
                "error": "invalid_intent",
                "detail": "Workflow is not ready for resume tailoring.",
            }
        is_dedicated_tailor = intent == WORKFLOW_INTENT_TAILOR_RESUME

        if opportunity_id:
            opportunity = self.opportunity_repo.get_for_user(user, opportunity_id)
            if opportunity is None:
                return {"error": "not_found", "detail": "Opportunity not found."}
        else:
            opportunity = self._create_opportunity_from_custom_jd(
                user,
                workflow,
                title=title or "Custom role",
                company=company or "Custom role",
                job_description=job_description or "",
            )

        workflow.status = WorkflowExecutionStatus.RUNNING
        workflow.save(update_fields=["status", "updated_at"])

        try:
            tailor_result = self.resume_tailor_agent.tailor(
                user, opportunity, workflow=workflow
            )
        except NoActiveResumeError as exc:
            workflow.status = WorkflowExecutionStatus.COMPLETED
            workflow.save(update_fields=["status", "updated_at"])
            return {"error": "no_resume", "detail": str(exc)}
        except Exception:
            workflow.status = WorkflowExecutionStatus.FAILED
            workflow.completed_at = timezone.now()
            workflow.save(update_fields=["status", "completed_at", "updated_at"])
            raise

        material = tailor_result["material"]
        planned_agents = result.get("planned_agents") or build_planned_agents(intent)
        completed_agents = list(result.get("completed_agents") or [])
        if is_dedicated_tailor and RESUME_TAILOR_AGENT_NAME not in completed_agents:
            completed_agents.append(RESUME_TAILOR_AGENT_NAME)

        updated_result = {
            **result,
            "tailor_selection_pending": False,
            "selected_opportunity_id": str(opportunity.id),
            "selected_target": {
                "opportunity_id": str(opportunity.id),
                "title": opportunity.job.title,
                "company": opportunity.job.company,
                "custom_jd": opportunity_id is None,
            },
            "tailored_material_id": str(material.id),
            "next_action": (
                f"Tailored resume ready for {opportunity.job.title} at "
                f"{opportunity.job.company}. Download PDF or review below."
            ),
        }
        if is_dedicated_tailor:
            updated_result["completed_agents"] = completed_agents
        workflow.result = updated_result
        workflow.status = WorkflowExecutionStatus.COMPLETED
        workflow.completed_at = timezone.now()
        workflow.save()

        return {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "opportunity_id": str(opportunity.id),
            "material": ApplicationMaterialSerializer(material).data,
            "agent_execution": AgentExecutionSerializer(tailor_result["execution"]).data,
            "reasoning_summary": tailor_result["reasoning_summary"],
            "planned_agents": planned_agents,
            "completed_agents": completed_agents,
        }

    def start_workflow(self, user, *, goal: str) -> dict:
        """Create workflow and dispatch background execution; returns immediately."""
        goal = goal.strip()
        name = goal[:80] if len(goal) > 80 else goal or "Career goal"
        intent_classification = build_intent_classification(goal)
        workflow_intent = intent_classification["intent"]
        planned_agents = intent_classification["planned_agents"]

        workflow = self.repo.create(
            user=user,
            name=name,
            goal=goal,
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now(),
            context={
                "workflow_intent": workflow_intent,
                "planned_agents": planned_agents,
            },
            result={
                "workflow_intent": workflow_intent,
                "intent_classification": intent_classification,
                "planned_agents": planned_agents,
                "completed_agents": [],
            },
        )

        dispatch_workflow(user.id, workflow.id, goal)

        return {
            "workflow": WorkflowExecutionSerializer(workflow).data,
        }

    def execute_workflow(
        self, user, workflow: WorkflowExecution, goal: str | None = None
    ) -> dict:
        """Run workflow through LangGraph orchestration."""
        goal = (goal or workflow.goal or "").strip()
        try:
            return LangGraphWorkflowRunner().run(self, user, workflow, goal)
        except Exception as exc:
            logger.exception("Workflow %s execution failed", workflow.id)
            workflow.refresh_from_db()
            workflow.status = WorkflowExecutionStatus.FAILED
            workflow.error_message = str(exc)
            workflow.completed_at = timezone.now()
            workflow.save(
                update_fields=["status", "error_message", "completed_at", "updated_at"]
            )
            raise

    def _apply_rerun_context_overrides(
        self, workflow: WorkflowExecution, user, overrides: dict | None
    ) -> dict:
        context = dict(workflow.context or self.planner.build_context(user, workflow.goal))
        if overrides:
            search_overrides = dict(context.get("search_overrides") or {})
            search_overrides.update(
                {k: v for k, v in overrides.items() if v is not None}
            )
            context["search_overrides"] = search_overrides
            prefs = dict(context.get("preferences") or {})
            if overrides.get("remote_preference"):
                prefs["remote_preference"] = overrides["remote_preference"]
            if overrides.get("location"):
                prefs["target_locations"] = [overrides["location"]]
            if overrides.get("query"):
                prefs["target_roles"] = [overrides["query"]]
            context["preferences"] = prefs

        workflow.context = context
        workflow.save(update_fields=["context", "updated_at"])
        return context

    def _prepare_workflow_for_rerun(
        self, workflow: WorkflowExecution, *, overrides: dict | None = None
    ) -> None:
        existing_result = dict(workflow.result or {})
        completed = [
            agent
            for agent in existing_result.get("completed_agents") or []
            if agent not in RERUN_PIPELINE_AGENTS
        ]
        if PLANNER_AGENT_NAME not in completed:
            completed.insert(0, PLANNER_AGENT_NAME)

        workflow.status = WorkflowExecutionStatus.RUNNING
        workflow.error_message = ""
        workflow.completed_at = None
        rerun_result = {
            **existing_result,
            "completed_agents": completed,
            "last_search_overrides": overrides or {},
            "search_rerun_in_progress": True,
            "search_rerun_started_at": timezone.now().isoformat(),
            "tailor_selection_pending": False,
            "next_action": "",
        }
        rerun_result.pop("tailor_options", None)
        workflow.result = rerun_result
        workflow.save(
            update_fields=["status", "error_message", "completed_at", "result", "updated_at"]
        )

    def _resolve_rerun_tool_plan(self, workflow: WorkflowExecution) -> list[dict]:
        result = workflow.result or {}
        tool_plan = list(result.get("tool_plan") or [])
        filtered = [
            step for step in tool_plan if step.get("tool") in RERUN_PIPELINE_AGENTS
        ]
        if filtered:
            return filtered

        goal = workflow.goal or ""
        workflow_intent = result.get("workflow_intent") or classify_workflow_intent(goal)
        constraints = result.get("constraints") or extract_constraints_from_goal(goal)
        return build_default_tool_plan(workflow_intent, constraints)

    def _execute_rerun_job_search(
        self, user, workflow: WorkflowExecution, *, overrides: dict | None = None
    ) -> dict:
        context = self._apply_rerun_context_overrides(workflow, user, overrides)
        tool_plan = [
            step
            for step in self._resolve_rerun_tool_plan(workflow)
            if step.get("tool") in RERUN_PIPELINE_AGENTS
        ]
        return LangGraphRerunRunner().run(
            self,
            user,
            workflow,
            context=context,
            tool_plan=tool_plan,
            overrides=overrides,
        )

    def rerun_job_search(
        self, user, workflow_id, *, overrides: dict | None = None
    ) -> dict:
        workflow = self.get_execution(user, workflow_id)
        if workflow is None:
            return None

        self._apply_rerun_context_overrides(workflow, user, overrides)
        self._prepare_workflow_for_rerun(workflow, overrides=overrides)
        dispatch_rerun_job_search(user.id, workflow.id, overrides or {})

        workflow.refresh_from_db()
        return {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "status": WorkflowExecutionStatus.RUNNING,
            "dispatched": True,
        }
