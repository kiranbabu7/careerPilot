"""Workflow persistence layer — Phase 3 extension point."""

from apps.workflows.models import WorkflowExecution


class WorkflowRepository:
    def list_for_user(self, user) -> list[WorkflowExecution]:
        return list(WorkflowExecution.objects.filter(user=user))

    def create(self, user, **fields) -> WorkflowExecution:
        return WorkflowExecution.objects.create(user=user, **fields)
