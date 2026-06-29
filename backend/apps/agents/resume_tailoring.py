"""Resume Tailor agent — on-demand tailored resume generation."""

import logging

from django.utils import timezone

from apps.agents.material_context import (
    NoActiveResumeError,
    build_material_context,
    build_prompt_variables,
)
from apps.agents.models import AgentExecutionStatus
from apps.agents.repositories import AgentExecutionRepository
from apps.prompts.services import PromptService
from apps.resumes.materials_provider import ApplicationMaterialsProvider
from apps.resumes.models import ApplicationMaterialStatus, ApplicationMaterialType
from apps.resumes.pdf_export import (
    generate_ats_resume_pdf_with_engine,
    iter_pdf_smoke_errors,
)
from apps.resumes.repositories import ApplicationMaterialRepository

RESUME_TAILOR_AGENT_NAME = "resume_tailor"
RESUME_TAILOR_PROMPT_NAME = "resume_tailor"

logger = logging.getLogger(__name__)


class ResumeTailorAgent:
    def __init__(
        self,
        prompt_service: PromptService | None = None,
        provider: ApplicationMaterialsProvider | None = None,
        material_repo: ApplicationMaterialRepository | None = None,
        agent_repo: AgentExecutionRepository | None = None,
    ):
        self.prompt_service = prompt_service or PromptService()
        self.provider = provider or ApplicationMaterialsProvider()
        self.material_repo = material_repo or ApplicationMaterialRepository()
        self.agent_repo = agent_repo or AgentExecutionRepository()

    def tailor(self, user, opportunity, *, workflow=None) -> dict:
        started_at = timezone.now()
        workflow = workflow or opportunity.workflow_execution

        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=RESUME_TAILOR_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "opportunity_id": str(opportunity.id),
                "job_title": opportunity.job.title,
            },
            started_at=started_at,
        )

        try:
            context = build_material_context(user, opportunity)
            rendered = self.prompt_service.render(
                RESUME_TAILOR_PROMPT_NAME,
                build_prompt_variables(context),
            )
            result = self.provider.generate(
                rendered["rendered_text"],
                ApplicationMaterialType.TAILORED_RESUME,
            )

            pdf_metadata: dict = {"pdf_available": False, "pdf_engine": None}
            try:
                issues = list(iter_pdf_smoke_errors(result.content))
                if not issues:
                    _, pdf_engine = generate_ats_resume_pdf_with_engine(
                        result.content,
                        user=user,
                        resume_text=context["active_resume"].extracted_text or "",
                        target_locations=list(context["preferences"].target_locations or []),
                    )
                    pdf_metadata["pdf_available"] = True
                    pdf_metadata["pdf_engine"] = pdf_engine
            except Exception:
                logger.exception("Tailored resume PDF smoke check failed")

            material = self.material_repo.create(
                user=user,
                opportunity=opportunity,
                source_resume=context["active_resume"],
                material_type=ApplicationMaterialType.TAILORED_RESUME,
                content=result.content,
                prompt_name=rendered["name"],
                prompt_version=rendered["version"],
                model_name=result.model_name,
                status=ApplicationMaterialStatus.COMPLETED,
                metadata={
                    "prompt_source": rendered["source"],
                    "used_fallback": result.used_fallback,
                    "job_title": opportunity.job.title,
                    "job_company": opportunity.job.company,
                    **pdf_metadata,
                },
            )

            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            reasoning = (
                f"Tailored resume for '{opportunity.job.title}' at "
                f"{opportunity.job.company} using {result.model_name}."
            )

            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "opportunity_id": str(opportunity.id),
                "material_id": str(material.id),
                "material_type": material.material_type,
                "model_name": result.model_name,
                "used_fallback": result.used_fallback,
                "duration_ms": duration_ms,
            }
            execution.reasoning_summary = reasoning
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "material": material,
                "reasoning_summary": reasoning,
            }
        except NoActiveResumeError:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = (
                "No active resume found. Upload and activate a resume first."
            )
            execution.completed_at = completed_at
            execution.save()
            raise
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise
