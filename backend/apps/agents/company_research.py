"""Company Research agent — on-demand Tavily enrichment for a job's company."""

from collections.abc import Callable

from django.utils import timezone

from apps.agents.models import AgentExecutionStatus
from apps.agents.repositories import AgentExecutionRepository
from apps.jobs.repositories import JobRepository
from apps.providers.jobs.tavily_research import TavilyCompanyResearchProvider

COMPANY_RESEARCH_AGENT_NAME = "company_research"


class CompanyResearchAgent:
    def __init__(
        self,
        job_repo: JobRepository | None = None,
        tavily_provider: TavilyCompanyResearchProvider | None = None,
        agent_repo: AgentExecutionRepository | None = None,
    ):
        self.job_repo = job_repo or JobRepository()
        self.tavily_provider = tavily_provider or TavilyCompanyResearchProvider()
        self.agent_repo = agent_repo or AgentExecutionRepository()

    def _research_company(
        self,
        user,
        opportunity,
        *,
        workflow=None,
        parent_execution_id: str | None = None,
    ) -> dict:
        """Fetch and persist company research without creating an AgentExecution."""
        workflow = workflow or opportunity.workflow_execution
        job = opportunity.job

        research = self.tavily_provider.enrich_company(
            job.company,
            job_title=job.title,
        )

        self.job_repo.update(job, company_research=research)

        evaluation_result = None
        if research.get("available") and opportunity.match_score is not None:
            from apps.agents.job_evaluation import JobEvaluationAgent

            opportunity.job.refresh_from_db()
            evaluation_result = JobEvaluationAgent()._evaluate_opportunity(
                user,
                opportunity,
                workflow=workflow,
                execution_id=parent_execution_id,
            )

        if research.get("available"):
            reasoning = (
                f"Researched {job.company}: business overview, news, funding, "
                "and hiring context retrieved via Tavily."
            )
        else:
            reason = research.get("reason", "unavailable")
            error_detail = research.get("error", "")
            detail_suffix = (
                f": {error_detail}" if error_detail and error_detail != reason else ""
            )
            reasoning = (
                f"Company research for {job.company} unavailable ({reason}{detail_suffix}). "
                "Evaluation can still proceed without enrichment."
            )

        return {
            "opportunity_id": str(opportunity.id),
            "company": job.company,
            "job_title": job.title,
            "company_research": research,
            "available": research.get("available", False),
            "reason": research.get("reason", ""),
            "error": research.get("error", ""),
            "reasoning_summary": reasoning,
            "evaluation": evaluation_result,
        }

    def research(self, user, opportunity, *, workflow=None) -> dict:
        started_at = timezone.now()
        workflow = workflow or opportunity.workflow_execution
        job = opportunity.job

        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=COMPANY_RESEARCH_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "opportunity_id": str(opportunity.id),
                "company": job.company,
                "job_title": job.title,
            },
            started_at=started_at,
        )

        try:
            outcome = self._research_company(
                user,
                opportunity,
                workflow=workflow,
                parent_execution_id=str(execution.id),
            )

            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            research = outcome["company_research"]

            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "opportunity_id": outcome["opportunity_id"],
                "company": outcome["company"],
                "available": outcome["available"],
                "reason": outcome["reason"],
                "error": outcome["error"],
                "errors": research.get("errors", []),
                "duration_ms": duration_ms,
            }
            execution.reasoning_summary = outcome["reasoning_summary"]
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "company_research": research,
                "reasoning_summary": outcome["reasoning_summary"],
                "evaluation": outcome["evaluation"],
            }
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise

    def research_batch(
        self,
        user,
        opportunities: list,
        *,
        workflow=None,
        on_progress: Callable[[object, dict], None] | None = None,
    ) -> dict:
        """Research multiple companies under a single AgentExecution."""
        if not opportunities:
            return {
                "execution": None,
                "researched_count": 0,
                "available_count": 0,
                "results": [],
            }

        started_at = timezone.now()
        workflow = workflow or opportunities[0].workflow_execution
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=COMPANY_RESEARCH_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "opportunity_ids": [str(opportunity.id) for opportunity in opportunities],
                "batch_size": len(opportunities),
            },
            started_at=started_at,
        )
        parent_execution_id = str(execution.id)

        results = []
        available_count = 0

        try:
            for opportunity in opportunities:
                outcome = self._research_company(
                    user,
                    opportunity,
                    workflow=workflow,
                    parent_execution_id=parent_execution_id,
                )
                results.append(outcome)
                if outcome["available"]:
                    available_count += 1
                if on_progress:
                    on_progress(opportunity, outcome)

            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            researched_count = len(results)
            reasoning = (
                f"Researched {researched_count} "
                f"compan{'ies' if researched_count != 1 else 'y'}: "
                f"{available_count} with enrichment available."
            )

            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "researched_count": researched_count,
                "available_count": available_count,
                "duration_ms": duration_ms,
                "results": [
                    {
                        "opportunity_id": item["opportunity_id"],
                        "company": item["company"],
                        "job_title": item["job_title"],
                        "available": item["available"],
                        "reason": item["reason"],
                        "summary": (item["company_research"].get("summary") or "")[:200],
                    }
                    for item in results
                ],
            }
            execution.reasoning_summary = reasoning
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "researched_count": researched_count,
                "available_count": available_count,
                "results": results,
            }
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise
