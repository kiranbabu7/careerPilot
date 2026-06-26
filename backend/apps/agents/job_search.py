"""Job Search agent — coordinates job discovery through JobSearchService."""

from django.utils import timezone

from apps.agents.models import AgentExecutionStatus
from apps.agents.repositories import AgentExecutionRepository
from apps.jobs.serializers import OpportunityListSerializer
from apps.jobs.services import JobSearchService

JOB_SEARCH_AGENT_NAME = "job_search"


class JobSearchAgent:
    def __init__(
        self,
        search_service: JobSearchService | None = None,
        agent_repo: AgentExecutionRepository | None = None,
    ):
        self.search_service = search_service or JobSearchService()
        self.agent_repo = agent_repo or AgentExecutionRepository()

    def search(self, user, workflow, context: dict) -> dict:
        started_at = timezone.now()
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=JOB_SEARCH_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={"goal": context.get("goal"), "context": context},
            started_at=started_at,
        )

        try:
            result = self.search_service.search(user, workflow, context)
            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            opportunities_data = OpportunityListSerializer(
                result["opportunities"], many=True
            ).data

            output_data = {
                "discovered_count": result["discovered_count"],
                "total_listings": result["total_listings"],
                "provider_summary": result["provider_summary"],
                "duration_ms": duration_ms,
                "opportunity_ids": [o["id"] for o in opportunities_data],
            }

            has_errors = bool(result["errors"])
            status = (
                AgentExecutionStatus.COMPLETED
                if result["discovered_count"] > 0 or not has_errors
                else AgentExecutionStatus.COMPLETED
            )
            if has_errors and result["discovered_count"] == 0:
                status = AgentExecutionStatus.FAILED

            reasoning = self._build_summary(result)

            execution.status = status
            execution.output_data = output_data
            execution.reasoning_summary = reasoning
            execution.error_message = "; ".join(result["errors"]) if has_errors else ""
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "discovered_count": result["discovered_count"],
                "provider_summary": result["provider_summary"],
                "opportunities": result["opportunities"],
                "reasoning_summary": reasoning,
            }
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise

    def _build_summary(self, result: dict) -> str:
        count = result["discovered_count"]
        query = result["query"]
        providers = result["provider_summary"].get("providers", {})
        apify = providers.get("apify", {})
        tavily = providers.get("tavily_research", {})

        parts = [f"Job search for '{query}' found {count} opportunities."]
        if apify:
            parts.append(
                f"Apify: {apify.get('count', 0)} listings"
                f" ({apify.get('status', 'unknown')})."
            )
        if tavily:
            parts.append(
                f"Tavily enriched {tavily.get('companies_enriched', 0)} companies."
            )
        if result["errors"]:
            parts.append(f"Partial errors: {len(result['errors'])}.")
        return " ".join(parts)
