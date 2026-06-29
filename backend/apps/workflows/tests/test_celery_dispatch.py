"""Tests for Celery-based workflow dispatch."""

from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.resumes.tests.test_phase2 import user
from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus
from apps.workflows.services import WorkflowService
from apps.workflows.tasks import dispatch_workflow, run_workflow_task


@pytest.mark.django_db
class TestCeleryWorkflowDispatch:
    def test_dispatch_workflow_enqueues_celery_task(self, user):
        with patch("apps.workflows.tasks.run_workflow_task.delay") as mock_delay:
            dispatch_workflow(user.id, "workflow-id", "Find backend jobs")

        mock_delay.assert_called_once_with(user.id, "workflow-id", "Find backend jobs")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_run_workflow_task_executes_workflow_service(self, user):
        workflow = WorkflowExecution.objects.create(
            user=user,
            name="Test workflow",
            goal="Find backend jobs",
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        with patch.object(WorkflowService, "execute_workflow") as mock_execute:
            run_workflow_task(user.id, workflow.id, workflow.goal)

        mock_execute.assert_called_once()
        called_user, called_workflow, called_goal = mock_execute.call_args[0]
        assert called_user.id == user.id
        assert called_workflow.id == workflow.id
        assert called_goal == workflow.goal

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_run_workflow_task_marks_failed_after_retries_exhausted(self, user):
        workflow = WorkflowExecution.objects.create(
            user=user,
            name="Failing workflow",
            goal="Fail",
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        with patch.object(
            WorkflowService,
            "execute_workflow",
            side_effect=RuntimeError("provider unavailable"),
        ), patch.object(run_workflow_task, "max_retries", 0):
            with pytest.raises(RuntimeError, match="provider unavailable"):
                run_workflow_task.apply(
                    args=(user.id, workflow.id, workflow.goal),
                    throw=True,
                )

        workflow.refresh_from_db()
        assert workflow.status == WorkflowExecutionStatus.FAILED
        assert "provider unavailable" in workflow.error_message

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_start_workflow_still_returns_immediately(self, user):
        service = WorkflowService()
        with patch("apps.workflows.tasks.run_workflow_task.delay") as mock_delay:
            result = service.start_workflow(user, goal="Find remote Python roles")

        mock_delay.assert_called_once()
        assert result["workflow"]["status"] == WorkflowExecutionStatus.RUNNING
        assert result["workflow"]["goal"] == "Find remote Python roles"
