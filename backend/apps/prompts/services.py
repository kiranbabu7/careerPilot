"""Prompt management — Phase 6 extension point."""

from apps.prompts.repositories import PromptRepository


class PromptService:
    def __init__(self, repo: PromptRepository | None = None):
        self.repo = repo or PromptRepository()

    def get_active_prompt(self, name: str):
        return self.repo.get_active(name)
