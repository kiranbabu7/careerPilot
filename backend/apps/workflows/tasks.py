"""Background workflow execution via Celery."""

import logging

from celery import shared_task
from django.db import close_old_connections
from django.utils import timezone

from apps.workflows.models import WorkflowExecutionStatus

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN_SECONDS = 5


def _get_user_and_workflow(user_id, workflow_id):
    from django.contrib.auth import get_user_model

    from apps.workflows.services import WorkflowService

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    workflow = WorkflowService().get_execution(user, workflow_id)
    return user, workflow


def _mark_workflow_failed(user_id, workflow_id, exc: Exception) -> None:
    from django.contrib.auth import get_user_model

    from apps.workflows.services import WorkflowService

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    workflow = WorkflowService().get_execution(user, workflow_id)
    if workflow is None or workflow.status == WorkflowExecutionStatus.FAILED:
        return

    workflow.status = WorkflowExecutionStatus.FAILED
    workflow.error_message = str(exc)
    workflow.completed_at = timezone.now()
    workflow.save(
        update_fields=["status", "error_message", "completed_at", "updated_at"]
    )


def _reset_workflow_for_retry(user_id, workflow_id) -> None:
    from django.contrib.auth import get_user_model

    from apps.workflows.services import WorkflowService

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    workflow = WorkflowService().get_execution(user, workflow_id)
    if workflow is None:
        return

    workflow.status = WorkflowExecutionStatus.RUNNING
    workflow.error_message = ""
    workflow.completed_at = None
    workflow.save(
        update_fields=["status", "error_message", "completed_at", "updated_at"]
    )


@shared_task(bind=True, max_retries=1, name="workflows.run_workflow")
def run_workflow_task(self, user_id, workflow_id, goal: str) -> None:
    """Execute a workflow in the background with one retry on transient failure."""
    close_old_connections()
    try:
        from apps.workflows.services import WorkflowService

        user, workflow = _get_user_and_workflow(user_id, workflow_id)
        if workflow is None:
            logger.error("Workflow %s not found for user %s", workflow_id, user_id)
            return

        WorkflowService().execute_workflow(user, workflow, goal)
    except Exception as exc:
        logger.exception("Background workflow %s failed", workflow_id)
        _mark_workflow_failed(user_id, workflow_id, exc)
        if self.request.retries < self.max_retries:
            _reset_workflow_for_retry(user_id, workflow_id)
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN_SECONDS) from exc
        raise
    finally:
        close_old_connections()


def dispatch_workflow(user_id, workflow_id, goal: str) -> None:
    """Enqueue workflow execution so the HTTP request returns immediately."""
    run_workflow_task.delay(user_id, workflow_id, goal)


@shared_task(bind=True, max_retries=1, name="workflows.rerun_job_search")
def run_rerun_job_search_task(self, user_id, workflow_id, overrides=None) -> None:
    """Re-run job search and evaluation in the background."""
    close_old_connections()
    try:
        from apps.workflows.services import WorkflowService

        user, workflow = _get_user_and_workflow(user_id, workflow_id)
        if workflow is None:
            logger.error("Workflow %s not found for rerun (user %s)", workflow_id, user_id)
            return

        WorkflowService()._execute_rerun_job_search(
            user, workflow, overrides=overrides or {}
        )
    except Exception as exc:
        logger.exception("Background job search rerun for %s failed", workflow_id)
        _mark_workflow_failed(user_id, workflow_id, exc)
        if self.request.retries < self.max_retries:
            _reset_workflow_for_retry(user_id, workflow_id)
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN_SECONDS) from exc
        raise
    finally:
        close_old_connections()


def dispatch_rerun_job_search(user_id, workflow_id, overrides=None) -> None:
    """Enqueue job search rerun so the HTTP request returns immediately."""
    run_rerun_job_search_task.delay(user_id, workflow_id, overrides or {})
