"""Shared LLM provider for application material generation."""

import json
import logging
import re
from dataclasses import dataclass

from django.conf import settings

from apps.providers.llm.openrouter_chat import invoke_openrouter, openrouter_configured
from apps.resumes.providers import RESUME_ANALYSIS_MODEL
logger = logging.getLogger(__name__)


@dataclass
class MaterialGenerationResult:
    content: str
    model_name: str
    used_fallback: bool = False


class ApplicationMaterialsProvider:
    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "").rstrip("/")
        self.model = RESUME_ANALYSIS_MODEL

    def generate(self, prompt_text: str, material_type: str) -> MaterialGenerationResult:
        if self._ai_configured():
            try:
                return self._call_ai(prompt_text)
            except Exception:
                logger.exception(
                    "AI application material generation failed; using local fallback"
                )
        return self._local_fallback(prompt_text, material_type)

    def _ai_configured(self) -> bool:
        return openrouter_configured()

    def _call_ai(self, prompt_text: str) -> MaterialGenerationResult:
        content = invoke_openrouter(
            prompt_text,
            model=self.model,
            temperature=0.4,
            timeout=90,
        )
        content = self._strip_fences(content)
        return MaterialGenerationResult(
            content=content,
            model_name=self.model,
            used_fallback=False,
        )

    def _local_fallback(self, prompt_text: str, material_type: str) -> MaterialGenerationResult:
        job_title = self._extract_field(prompt_text, "Title:")
        job_company = self._extract_field(prompt_text, "Company:")
        resume_excerpt = self._extract_section(prompt_text, "## Source resume")
        if material_type == "cover_letter":
            content = (
                f"Dear Hiring Manager,\n\n"
                f"I am excited to apply for the {job_title or 'open'} role at "
                f"{job_company or 'your company'}. My background aligns with the "
                f"requirements described in the posting.\n\n"
                f"{resume_excerpt[:500].strip()}\n\n"
                f"I would welcome the opportunity to discuss how I can contribute to "
                f"{job_company or 'your team'}.\n\n"
                f"---\n"
                f"*Deterministic local draft — configure OPENAI_API_KEY and "
                f"OPENROUTER_BASE_URL for AI-powered tailoring.*"
            )
        else:
            payload = {
                "professional_summary": (
                    f"Experienced professional seeking the {job_title or 'target'} role at "
                    f"{job_company or 'the company'}. Resume tailored to highlight relevant "
                    f"skills and experience from the source document."
                ),
                "skills": [
                    {
                        "category": "Core Skills:",
                        "items": "Relevant skills drawn from source resume and job requirements",
                    }
                ],
                "experience": [
                    {
                        "title": "Professional Experience",
                        "dates": "See source resume",
                        "description": "",
                        "bullets": [
                            line.strip("-* ").strip()
                            for line in resume_excerpt.splitlines()
                            if line.strip().startswith(("-", "*", "•"))
                        ][:6]
                        or [resume_excerpt[:500].strip() or "See source resume for details."],
                    }
                ],
                "education": [],
            }
            content = json.dumps(payload, indent=2)
        return MaterialGenerationResult(
            content=content,
            model_name="local-fallback",
            used_fallback=True,
        )

    @staticmethod
    def _strip_fences(content: str) -> str:
        fence_match = re.search(r"```(?:json|markdown|md)?\s*([\s\S]*?)```", content)
        if fence_match:
            return fence_match.group(1).strip()
        return content.strip()

    @staticmethod
    def _extract_field(text: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}\s*(.+)", text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_section(text: str, heading: str) -> str:
        pattern = rf"{re.escape(heading)}\s*\n+([\s\S]*?)(?:\n## |\Z)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else text[-1500:]

