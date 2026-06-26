"""Planner agent — Phase 3 shell for workflow orchestration."""

from django.utils import timezone

from apps.agents.models import AgentExecution, AgentExecutionStatus
from apps.agents.repositories import AgentExecutionRepository
from apps.memory.services import MemoryService
from apps.resumes.repositories import ResumeAnalysisRepository, ResumeRepository
from apps.users.repositories import UserPreferenceRepository

PLANNER_AGENT_NAME = "planner"


class PlannerAgent:
    def __init__(
        self,
        preference_repo: UserPreferenceRepository | None = None,
        resume_repo: ResumeRepository | None = None,
        analysis_repo: ResumeAnalysisRepository | None = None,
        agent_repo: AgentExecutionRepository | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.resume_repo = resume_repo or ResumeRepository()
        self.analysis_repo = analysis_repo or ResumeAnalysisRepository()
        self.agent_repo = agent_repo or AgentExecutionRepository()
        self.memory_service = memory_service or MemoryService()

    def build_context(self, user, goal: str) -> dict:
        preference, _ = self.preference_repo.get_or_create_for_user(user)
        active_resume = self.resume_repo.get_active_for_user(user)
        active_analysis = (
            self.analysis_repo.get_latest_for_resume(active_resume)
            if active_resume
            else None
        )
        memory_context = self.memory_service.get_user_context(user)

        return {
            "goal": goal,
            "preferences": {
                "target_roles": preference.target_roles,
                "target_locations": preference.target_locations,
                "remote_preference": preference.remote_preference,
                "career_goals": preference.career_goals,
                "skills": preference.skills,
            },
            "active_resume": (
                {
                    "id": str(active_resume.id),
                    "filename": active_resume.original_filename,
                    "health_score": active_analysis.health_score if active_analysis else None,
                    "ats_score": active_analysis.ats_score if active_analysis else None,
                }
                if active_resume
                else None
            ),
            "memory_snippets": [
                entry["content"] for entry in memory_context.get("memories", [])[:5]
            ],
        }

    def plan(self, user, workflow, goal: str) -> dict:
        context = self.build_context(user, goal)
        plan_summary = self._generate_plan_summary(context)
        suggested_steps = self._suggest_steps(context)

        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=PLANNER_AGENT_NAME,
            status=AgentExecutionStatus.COMPLETED,
            input_data={"goal": goal, "context": context},
            output_data={"suggested_steps": suggested_steps},
            reasoning_summary=plan_summary,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )

        return {
            "execution": execution,
            "plan_summary": plan_summary,
            "suggested_steps": suggested_steps,
            "context": context,
        }

    def _generate_plan_summary(self, context: dict) -> str:
        goal = context.get("goal", "").strip()
        roles = context.get("preferences", {}).get("target_roles", [])
        role_phrase = roles[0] if roles else "your target roles"
        resume = context.get("active_resume")

        parts = [f"Planning workflow for: {goal}"]
        if roles:
            parts.append(f"Aligned with target role: {role_phrase}.")
        if resume:
            parts.append(
                f"Using active resume ({resume['filename']}) "
                f"with health score {resume.get('health_score', '—')}."
            )
        else:
            parts.append("Resume not yet uploaded — profile completion recommended first.")
        parts.append(
            "Job search runs automatically after planning to discover matching opportunities."
        )
        return " ".join(parts)

    def _suggest_steps(self, context: dict) -> list[dict]:
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
        steps.append({
            "key": "discover_opportunities",
            "title": "Discover opportunities",
            "description": "Job search providers scan LinkedIn, Indeed, and other boards.",
        })
        steps.append({
            "key": "research_companies",
            "title": "Research target companies",
            "description": "Tavily enriches discovered roles with company news and context.",
        })
        return steps
