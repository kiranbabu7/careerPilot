"""Workflow persistence layer — Phase 3 extension point."""

from datetime import timedelta

from django.db.models import Count, Max
from django.utils import timezone

from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus, WorkflowMessage

DEFAULT_STALE_WORKFLOW_MINUTES = 120


class WorkflowRepository:
    def list_for_user(self, user) -> list[WorkflowExecution]:
        return list(
            WorkflowExecution.objects.filter(user=user)
            .annotate(
                agent_run_count=Count("agent_executions"),
                last_agent_at=Max("agent_executions__created_at"),
            )
            .order_by("-created_at")
        )

    def create(self, user, **fields) -> WorkflowExecution:
        return WorkflowExecution.objects.create(user=user, **fields)

    def get_for_user(self, user, workflow_id) -> WorkflowExecution | None:
        return WorkflowExecution.objects.filter(user=user, id=workflow_id).first()

    def fail_stale_running_workflows(
        self,
        *,
        user=None,
        max_age_minutes: int = DEFAULT_STALE_WORKFLOW_MINUTES,
    ) -> list[WorkflowExecution]:
        """Mark long-running workflows as failed so they do not block scheduled jobs."""
        cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
        qs = WorkflowExecution.objects.filter(
            status=WorkflowExecutionStatus.RUNNING,
            started_at__lt=cutoff,
        )
        if user is not None:
            qs = qs.filter(user=user)

        stale = list(qs)
        for workflow in stale:
            workflow.status = WorkflowExecutionStatus.FAILED
            workflow.error_message = (
                "Workflow timed out after "
                f"{max_age_minutes} minutes without completing."
            )
            workflow.completed_at = timezone.now()
            workflow.save(
                update_fields=[
                    "status",
                    "error_message",
                    "completed_at",
                    "updated_at",
                ]
            )
        return stale


class WorkflowMessageRepository:
    def list_for_workflow(self, user, workflow_id) -> list[WorkflowMessage]:
        return list(
            WorkflowMessage.objects.filter(
                user=user,
                workflow_id=workflow_id,
            ).order_by("created_at")
        )

    def create(
        self,
        *,
        user,
        workflow: WorkflowExecution,
        role: str,
        content: str,
        actions: list | None = None,
        metadata: dict | None = None,
    ) -> WorkflowMessage:
        return WorkflowMessage.objects.create(
            user=user,
            workflow=workflow,
            role=role,
            content=content,
            actions=actions if actions is not None else [],
            metadata={} if metadata is None else metadata,
        )

    def get_latest_assistant_with_actions(
        self, user, workflow_id
    ) -> WorkflowMessage | None:
        return (
            WorkflowMessage.objects.filter(
                user=user,
                workflow_id=workflow_id,
                role="assistant",
            )
            .exclude(actions=[])
            .order_by("-created_at")
            .first()
        )

    def update_actions(self, message: WorkflowMessage, actions: list) -> WorkflowMessage:
        message.actions = actions
        message.save(update_fields=["actions", "updated_at"])
        return message
