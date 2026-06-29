"""Decision Agent — on-demand synthesis of next actions."""

from django.utils import timezone

from apps.agents.decision_context import (
    build_decision_context,
    build_decision_prompt_variables,
    context_to_json,
)
from apps.agents.decision_provider import DecisionProvider
from apps.agents.models import AgentExecutionStatus, DecisionRecommendationStatus
from apps.agents.repositories import (
    AgentExecutionRepository,
    DecisionRecommendationRepository,
)
from apps.memory.services import ActivityService, MemoryService
from apps.prompts.services import PromptService
from apps.workflows.repositories import WorkflowRepository

DECISION_AGENT_NAME = "decision"
DECISION_PROMPT_NAME = "decision"


class DecisionAgent:
    def __init__(
        self,
        prompt_service: PromptService | None = None,
        provider: DecisionProvider | None = None,
        decision_repo: DecisionRecommendationRepository | None = None,
        agent_repo: AgentExecutionRepository | None = None,
        workflow_repo: WorkflowRepository | None = None,
        activity_service: ActivityService | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.prompt_service = prompt_service or PromptService()
        self.provider = provider or DecisionProvider()
        self.decision_repo = decision_repo or DecisionRecommendationRepository()
        self.agent_repo = agent_repo or AgentExecutionRepository()
        self.workflow_repo = workflow_repo or WorkflowRepository()
        self.activity_service = activity_service or ActivityService()
        self.memory_service = memory_service or MemoryService()

    def generate(self, user, *, workflow_id=None) -> dict:
        workflow = None
        if workflow_id:
            workflow = self.workflow_repo.get_for_user(user, workflow_id)
            if workflow is None:
                raise ValueError("Workflow not found.")

        started_at = timezone.now()
        context = build_decision_context(user, workflow=workflow)
        input_snapshot = context_to_json(context)

        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=DECISION_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data=input_snapshot,
            started_at=started_at,
        )

        recommendation = self.decision_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_execution=execution,
            status=DecisionRecommendationStatus.PENDING,
            input_snapshot=input_snapshot,
        )

        try:
            rendered = self.prompt_service.render(
                DECISION_PROMPT_NAME,
                build_decision_prompt_variables(context),
            )
            result = self.provider.generate(rendered["rendered_text"], context)

            reasoning = (
                f"Decision synthesis across {context['counts']['opportunities']} opportunities, "
                f"{context['counts']['applications']} applications, "
                f"{context['counts']['materials']} materials, and "
                f"{context['counts']['interview_plans']} interview plans "
                f"using {result.model_name}."
            )

            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "summary": result.summary,
                "rationale": result.rationale,
                "actions": result.actions,
                "used_fallback": result.used_fallback,
                "model_name": result.model_name,
                "decision_recommendation_id": str(recommendation.id),
            }
            execution.reasoning_summary = reasoning
            execution.completed_at = completed_at
            execution.save()

            recommendation.status = DecisionRecommendationStatus.COMPLETED
            recommendation.summary = result.summary
            recommendation.rationale = result.rationale
            recommendation.actions = result.actions
            recommendation.prompt_name = rendered["name"]
            recommendation.prompt_version = rendered["version"]
            recommendation.model_name = result.model_name
            recommendation.save()

            self.activity_service.record_decision_generated(user, recommendation)
            self.memory_service.record_decision_context(user, recommendation)

            return {
                "recommendation": recommendation,
                "execution": execution,
                "reasoning_summary": reasoning,
            }
        except Exception as exc:
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = timezone.now()
            execution.save()

            recommendation.status = DecisionRecommendationStatus.FAILED
            recommendation.save()
            raise
