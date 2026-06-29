"""Celery tasks for scheduled job search."""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.utils import timezone

from apps.jobs.scheduled_search import ScheduledJobSearchService
from apps.users.repositories import UserPreferenceRepository

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN_SECONDS = 5


@shared_task(name="jobs.check_job_search_schedules")
def check_job_search_schedules() -> int:
    """Enqueue scheduled job searches for users whose next run is due."""
    close_old_connections()
    try:
        from apps.workflows.repositories import WorkflowRepository

        WorkflowRepository().fail_stale_running_workflows()
        due_preferences = UserPreferenceRepository().list_due_scheduled_searches()
        for preference in due_preferences:
            run_scheduled_job_search.delay(preference.user_id)
        logger.info(
            "check_job_search_schedules enqueued=%s checked_at=%s",
            len(due_preferences),
            timezone.now().isoformat(),
        )
        return len(due_preferences)
    finally:
        close_old_connections()


@shared_task(
    bind=True,
    max_retries=1,
    name="jobs.run_scheduled_job_search",
)
def run_scheduled_job_search(self, user_id) -> dict:
    """Run the scheduled job search pipeline for a single user."""
    close_old_connections()
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("Scheduled job search user %s not found", user_id)
        return {"status": "skipped", "reason": "user_not_found"}

    try:
        result = ScheduledJobSearchService().run_for_user(user)
        return {
            "status": result.status,
            "reason": result.reason,
            "workflow_id": result.workflow_id,
            "discovered_count": result.discovered_count,
            "evaluated_count": result.evaluated_count,
        }
    except Exception as exc:
        logger.exception("Scheduled job search failed for user %s", user_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN_SECONDS) from exc
        return {"status": "failed", "reason": str(exc)}
    finally:
        close_old_connections()
