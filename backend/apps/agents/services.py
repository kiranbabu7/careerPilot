"""Agent orchestration — Phase 3 extension point."""

from apps.agents.repositories import AgentExecutionRepository


class AgentService:
    def __init__(self, repo: AgentExecutionRepository | None = None):
        self.repo = repo or AgentExecutionRepository()

    def list_executions(self, user):
        return self.repo.list_for_user(user)
