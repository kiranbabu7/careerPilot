"""Prompt management — DB-first with filesystem fallback."""

import re
from pathlib import Path

from apps.prompts.repositories import PromptRepository

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class MissingPromptVariablesError(ValueError):
    def __init__(self, name: str, missing: set[str]):
        self.name = name
        self.missing = missing
        super().__init__(
            f"Missing prompt variables for '{name}': {', '.join(sorted(missing))}"
        )


class PromptNotFoundError(FileNotFoundError):
    pass


class PromptService:
    def __init__(self, repo: PromptRepository | None = None):
        self.repo = repo or PromptRepository()

    def get_active_prompt(self, name: str):
        return self.repo.get_active(name)

    def render(self, name: str, variables: dict) -> dict:
        """Render a prompt by name using DB version first, then filesystem fallback."""
        prompt_version = self.repo.get_active(name)
        if prompt_version:
            template = prompt_version.template
            version = prompt_version.version
            source = "db"
        else:
            template, version = self._load_filesystem_template(name)
            source = "filesystem"

        required = set(re.findall(r"\{(\w+)\}", template))
        missing = required - set(variables.keys())
        if missing:
            raise MissingPromptVariablesError(name, missing)

        rendered = template.format(**variables)
        return {
            "name": name,
            "version": version,
            "source": source,
            "rendered_text": rendered,
        }

    def _load_filesystem_template(self, name: str) -> tuple[str, int]:
        path = TEMPLATES_DIR / name / "v1.md"
        if not path.exists():
            raise PromptNotFoundError(f"No prompt template found for '{name}'")
        return path.read_text(encoding="utf-8"), 1
