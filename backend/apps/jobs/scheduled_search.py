"""Scheduled job search orchestration — Celery Beat driven discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from apps.agents.job_search import JobSearchAgent
from apps.agents.planner import PlannerAgent
from apps.agents.serializers import AgentExecutionSerializer
from apps.memory.services import ActivityService
from apps.providers.jobs.apify import ApifyJobsProvider
from apps.users.models import UserPreference
from apps.users.repositories import UserPreferenceRepository
from apps.workflows.models import WorkflowExecutionStatus
from apps.workflows.repositories import WorkflowRepository
from apps.workflows.services import WorkflowService

logger = logging.getLogger(__name__)

SCHEDULED_GOAL = "Scheduled job search"
VALID_SCHEDULE_INTERVALS = {60, 240, 720, 1440}


@dataclass
class ScheduledRunResult:
    status: str
    reason: str = ""
    workflow_id: str | None = None
    discovered_count: int = 0
    evaluated_count: int = 0
    accepted_count: int = 0
    borderline_count: int = 0
    rejected_count: int = 0
    duration_ms: int = 0
    metadata: dict = field(default_factory=dict)


class ScheduledJobSearchService:
    def __init__(
        self,
        *,
        workflow_repo: WorkflowRepository | None = None,
        workflow_service: WorkflowService | None = None,
        preference_repo: UserPreferenceRepository | None = None,
        planner: PlannerAgent | None = None,
        job_search_agent: JobSearchAgent | None = None,
        activity_service: ActivityService | None = None,
        apify_provider: ApifyJobsProvider | None = None,
    ):
        self.workflow_repo = workflow_repo or WorkflowRepository()
        self.workflow_service = workflow_service or WorkflowService()
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.planner = planner or PlannerAgent()
        self.job_search_agent = job_search_agent or JobSearchAgent()
        self.activity_service = activity_service or ActivityService()
        self.apify_provider = apify_provider or ApifyJobsProvider()

    def run_for_user(self, user) -> ScheduledRunResult:
        started_at = timezone.now()
        preference, _ = self.preference_repo.get_or_create_for_user(user)

        self.workflow_repo.fail_stale_running_workflows(user=user)

        if not preference.job_search_schedule_enabled:
            return self._skipped(
                user,
                preference,
                reason="schedule_disabled",
                message="Scheduled search is disabled.",
            )

        if not self._is_apify_configured():
            return self._skipped(
                user,
                preference,
                reason="apify_not_configured",
                message="Apify is not configured.",
            )

        if self._has_running_workflow(user):
            return self._skipped(
                user,
                preference,
                reason="workflow_running",
                message="A workflow is already running for this user.",
            )

        if not self._has_search_preferences(preference):
            return self._skipped(
                user,
                preference,
                reason="missing_preferences",
                message="Target roles or career goals are required.",
            )

        posted_since = self._resolve_posted_since(preference)
        context = self.planner.build_context(user, SCHEDULED_GOAL)
        context["trigger"] = "scheduled"

        workflow = self.workflow_repo.create(
            user=user,
            name="Scheduled job search",
            goal=SCHEDULED_GOAL,
            status=WorkflowExecutionStatus.RUNNING,
            started_at=started_at,
            context=context,
            result={
                "trigger": "scheduled",
                "planned_agents": ["job_search", "job_evaluation"],
                "completed_agents": [],
            },
        )

        logger.info(
            "scheduled_job_search.started user_id=%s workflow_id=%s posted_since=%s",
            user.id,
            workflow.id,
            posted_since.isoformat(),
        )

        try:
            job_search_result = self.job_search_agent.search(
                user,
                workflow,
                context,
                posted_since=posted_since,
            )
            self.workflow_service._append_completed_agent(workflow, "job_search")

            workflow.result = {
                **(workflow.result or {}),
                "discovered_count": job_search_result["discovered_count"],
                "provider_summary": job_search_result["provider_summary"],
                "job_search_summary": job_search_result["reasoning_summary"],
                "posted_since": posted_since.isoformat(),
            }
            workflow.save(update_fields=["result", "updated_at"])

            evaluation_summary = self.workflow_service._evaluate_discovered_opportunities(
                user, workflow, context
            )
            if evaluation_summary["evaluated_count"] > 0:
                self.workflow_service._append_completed_agent(workflow, "job_evaluation")

            completed_at = timezone.now()
            workflow.result = {
                **(workflow.result or {}),
                "evaluated_count": evaluation_summary["evaluated_count"],
                "accepted_count": evaluation_summary["accepted_count"],
                "borderline_count": evaluation_summary["borderline_count"],
                "rejected_count": evaluation_summary["rejected_count"],
                "top_match_score": evaluation_summary["top_match_score"],
            }
            workflow.status = WorkflowExecutionStatus.COMPLETED
            workflow.completed_at = completed_at
            workflow.save()

            self.workflow_service._seed_welcome_chat_message(user, workflow)

            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            discovered = job_search_result["discovered_count"]
            evaluated = evaluation_summary["evaluated_count"]
            if discovered == 0:
                apify_count = (
                    job_search_result.get("provider_summary", {})
                    .get("providers", {})
                    .get("apify", {})
                    .get("count", 0)
                )
                if apify_count:
                    summary = (
                        "Search completed; no new roles since last check "
                        f"(Apify returned {apify_count} listings)."
                    )
                else:
                    summary = "Search completed; no new roles found."
            else:
                summary = f"Discovered {discovered} roles; evaluated {evaluated}."
            self._mark_successful_run(preference, completed_at, message=summary)

            self.activity_service.record_scheduled_search(
                user,
                workflow,
                summary=summary,
                metadata={
                    "discovered_count": job_search_result["discovered_count"],
                    "evaluated_count": evaluation_summary["evaluated_count"],
                    "accepted_count": evaluation_summary["accepted_count"],
                    "duration_ms": duration_ms,
                },
            )

            logger.info(
                "scheduled_job_search.completed user_id=%s workflow_id=%s "
                "discovered=%s evaluated=%s duration_ms=%s",
                user.id,
                workflow.id,
                job_search_result["discovered_count"],
                evaluation_summary["evaluated_count"],
                duration_ms,
            )

            return ScheduledRunResult(
                status="completed",
                workflow_id=str(workflow.id),
                discovered_count=job_search_result["discovered_count"],
                evaluated_count=evaluation_summary["evaluated_count"],
                accepted_count=evaluation_summary["accepted_count"],
                borderline_count=evaluation_summary["borderline_count"],
                rejected_count=evaluation_summary["rejected_count"],
                duration_ms=duration_ms,
                metadata={
                    "job_search_execution": AgentExecutionSerializer(
                        job_search_result["execution"]
                    ).data,
                    "evaluation_executions": evaluation_summary["evaluation_executions"],
                },
            )
        except Exception as exc:
            logger.exception(
                "scheduled_job_search.failed user_id=%s workflow_id=%s",
                user.id,
                workflow.id,
            )
            workflow.refresh_from_db()
            workflow.status = WorkflowExecutionStatus.FAILED
            workflow.error_message = str(exc)
            workflow.completed_at = timezone.now()
            workflow.save(
                update_fields=["status", "error_message", "completed_at", "updated_at"]
            )
            raise

    def _skipped(
        self,
        user,
        preference: UserPreference,
        *,
        reason: str,
        message: str,
    ) -> ScheduledRunResult:
        logger.info(
            "scheduled_job_search.skipped user_id=%s reason=%s",
            user.id,
            reason,
        )
        self._record_schedule_attempt(
            preference,
            outcome=f"skipped:{reason}",
            message=message,
        )
        self.activity_service.record_scheduled_search(
            user,
            workflow=None,
            summary=message,
            metadata={"status": "skipped", "reason": reason},
        )
        return ScheduledRunResult(status="skipped", reason=reason, metadata={"message": message})

    def _is_apify_configured(self) -> bool:
        return bool(self.apify_provider.api_token and self.apify_provider.actor_ids)

    def _has_running_workflow(self, user) -> bool:
        from apps.workflows.models import WorkflowExecution

        return WorkflowExecution.objects.filter(
            user=user,
            status=WorkflowExecutionStatus.RUNNING,
        ).exists()

    def _has_search_preferences(self, preference: UserPreference) -> bool:
        roles = [role.strip() for role in (preference.target_roles or []) if role.strip()]
        career_goals = (preference.career_goals or "").strip()
        return bool(roles or career_goals)

    def _resolve_posted_since(self, preference: UserPreference):
        if preference.last_job_search_at:
            return preference.last_job_search_at

        interval = preference.job_search_schedule_interval_minutes or 60
        return timezone.now() - timedelta(minutes=interval)

    def _mark_successful_run(
        self,
        preference: UserPreference,
        completed_at,
        *,
        message: str = "",
    ) -> None:
        interval = preference.job_search_schedule_interval_minutes or 60
        preference.last_job_search_at = completed_at
        preference.last_scheduled_run_at = completed_at
        preference.next_scheduled_run_at = completed_at + timedelta(minutes=interval)
        preference.last_schedule_message = message
        preference.save(
            update_fields=[
                "last_job_search_at",
                "last_scheduled_run_at",
                "next_scheduled_run_at",
                "last_schedule_message",
                "updated_at",
            ]
        )

    def _record_schedule_attempt(
        self,
        preference: UserPreference,
        *,
        outcome: str,
        message: str,
    ) -> None:
        now = timezone.now()
        interval = preference.job_search_schedule_interval_minutes or 60
        preference.last_scheduled_run_at = now
        preference.last_schedule_message = message
        preference.next_scheduled_run_at = now + timedelta(minutes=interval)
        preference.save(
            update_fields=[
                "last_scheduled_run_at",
                "last_schedule_message",
                "next_scheduled_run_at",
                "updated_at",
            ]
        )


def compute_next_scheduled_run_at(
    *,
    enabled: bool,
    interval_minutes: int | None,
    from_time=None,
):
    if not enabled or not interval_minutes:
        return None
    base = from_time or timezone.now()
    return base + timedelta(minutes=interval_minutes)
