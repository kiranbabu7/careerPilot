"""Agent execution persistence — Phase 3 extension point."""

from apps.agents.models import AgentExecution


class AgentExecutionRepository:
    def list_for_user(self, user) -> list[AgentExecution]:
        return list(
            AgentExecution.objects.filter(user=user).order_by("-created_at")
        )

    def create(self, user, **fields) -> AgentExecution:
        return AgentExecution.objects.create(user=user, **fields)

    def get_for_workflow(self, workflow, agent_name: str) -> AgentExecution | None:
        return (
            AgentExecution.objects.filter(
                workflow_execution=workflow,
                agent_name=agent_name,
            )
            .order_by("-created_at")
            .first()
        )
