"""Interview Prep agent — on-demand interview preparation plans."""

from django.utils import timezone

from apps.agents.interview_context import (
    build_interview_context,
    build_interview_prompt_variables,
)
from apps.agents.models import AgentExecutionStatus
from apps.agents.repositories import AgentExecutionRepository
from apps.applications.interview_provider import InterviewPrepProvider
from apps.applications.models import InterviewPlanStatus
from apps.applications.repositories import InterviewPlanRepository
from apps.prompts.services import PromptService

INTERVIEW_PREP_AGENT_NAME = "interview_prep"
INTERVIEW_PREP_PROMPT_NAME = "interview_prep"


class InterviewPrepAgent:
    def __init__(
        self,
        prompt_service: PromptService | None = None,
        provider: InterviewPrepProvider | None = None,
        plan_repo: InterviewPlanRepository | None = None,
        agent_repo: AgentExecutionRepository | None = None,
    ):
        self.prompt_service = prompt_service or PromptService()
        self.provider = provider or InterviewPrepProvider()
        self.plan_repo = plan_repo or InterviewPlanRepository()
        self.agent_repo = agent_repo or AgentExecutionRepository()

    def generate(
        self,
        user,
        opportunity,
        *,
        application=None,
        interview=None,
        workflow=None,
    ) -> dict:
        started_at = timezone.now()
        workflow = workflow or opportunity.workflow_execution

        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=INTERVIEW_PREP_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "opportunity_id": str(opportunity.id),
                "application_id": str(application.id) if application else None,
                "interview_id": str(interview.id) if interview else None,
                "job_title": opportunity.job.title,
            },
            started_at=started_at,
        )

        try:
            context = build_interview_context(
                user, opportunity, application, interview=interview
            )
            rendered = self.prompt_service.render(
                INTERVIEW_PREP_PROMPT_NAME,
                build_interview_prompt_variables(context),
            )
            result = self.provider.generate(rendered["rendered_text"])

            section_count = sum(
                len(result.content.get(key, []))
                for key in (
                    "prep_roadmap",
                    "likely_questions",
                    "system_design_topics",
                    "company_talking_points",
                    "resume_stories",
                    "gaps_to_practice",
                )
            )
            reasoning = (
                f"Interview prep for '{opportunity.job.title}' at "
                f"{opportunity.job.company} — {section_count} prep items across "
                f"roadmap, questions, and practice areas using {result.model_name}."
            )

            plan = self.plan_repo.create(
                user=user,
                opportunity=opportunity,
                application=application,
                interview=interview,
                prompt_name=rendered["name"],
                prompt_version=rendered["version"],
                model_name=result.model_name,
                content=result.content,
                markdown=result.markdown,
                status=InterviewPlanStatus.COMPLETED,
                metadata={
                    "prompt_source": rendered["source"],
                    "used_fallback": result.used_fallback,
                    "reasoning_summary": reasoning,
                    "job_title": opportunity.job.title,
                    "job_company": opportunity.job.company,
                    "application_stage": context.get("application_stage"),
                    "interview_id": str(interview.id) if interview else None,
                    "interview_round": context.get("interview_round"),
                    "interview_format": context.get("interview_format"),
                },
            )

            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "opportunity_id": str(opportunity.id),
                "application_id": str(application.id) if application else None,
                "interview_plan_id": str(plan.id),
                "model_name": result.model_name,
                "used_fallback": result.used_fallback,
                "section_count": section_count,
                "duration_ms": duration_ms,
            }
            execution.reasoning_summary = reasoning
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "plan": plan,
                "reasoning_summary": reasoning,
            }
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise
