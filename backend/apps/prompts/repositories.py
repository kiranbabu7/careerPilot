"""Prompt version persistence — Phase 6 extension point."""

from apps.prompts.models import PromptVersion


class PromptRepository:
    def get_active(self, name: str) -> PromptVersion | None:
        return (
            PromptVersion.objects.filter(name=name, is_active=True)
            .order_by("-version")
            .first()
        )
