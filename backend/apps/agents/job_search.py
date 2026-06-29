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

    def search(self, user, workflow, context: dict, *, posted_since=None) -> dict:
        started_at = timezone.now()
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=JOB_SEARCH_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "goal": context.get("goal"),
                "context": context,
                "posted_since": posted_since.isoformat() if posted_since else None,
            },
            started_at=started_at,
        )

        try:
            result = self.search_service.search(
                user, workflow, context, posted_since=posted_since
            )
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
        location = result.get("location", "")
        providers = result["provider_summary"].get("providers", {})
        apify = providers.get("apify", {})
        tavily = providers.get("tavily_research", {})

        location_phrase = f" in {location}" if location else ""
        parts = [
            f"Job search for '{query}'{location_phrase} found {count} opportunities."
        ]
        if apify:
            apify_line = (
                f"Apify: {apify.get('count', 0)} listings"
                f" ({apify.get('status', 'unknown')})."
            )
            if apify.get("error"):
                apify_line += f" Error: {apify['error']}"
            parts.append(apify_line)
        if tavily:
            parts.append(
                f"Tavily enriched {tavily.get('companies_enriched', 0)} companies."
            )
        if count == 0 and not result["errors"]:
            if apify.get("configured", False):
                parts.append(
                    "No listings matched. Update target roles and locations in your profile."
                )
            else:
                parts.append(
                    "Configure Apify (APIFY_API_TOKEN and APIFY_JOB_ACTOR_IDS) "
                    "to enable discovery."
                )
        if result["errors"]:
            parts.append(f"Partial errors: {len(result['errors'])}.")
        return " ".join(parts)
