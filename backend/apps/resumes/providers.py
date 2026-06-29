"""AI-powered resume analysis provider."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from apps.providers.llm.json_output import parse_json_content
from apps.providers.llm.openrouter_chat import (
    DEFAULT_OPENROUTER_MODEL,
    invoke_openrouter,
    openrouter_configured,
)

logger = logging.getLogger(__name__)

# Resume analysis uses Gemini 2.5 Flash via OpenRouter exclusively.
RESUME_ANALYSIS_MODEL = DEFAULT_OPENROUTER_MODEL

PROMPT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "templates"
    / "resume_analysis"
    / "v1.md"
)


@dataclass
class AnalysisResult:
    model_name: str
    raw_summary: str
    health_score: int
    ats_score: int
    strengths: list[str]
    weaknesses: list[str]
    missing_keywords: list[str]
    improvement_suggestions: list[str]
    extracted_skills: list[str]
    used_fallback: bool = False


class ResumeAnalysisProvider:
    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "").rstrip("/")
        self.model = RESUME_ANALYSIS_MODEL

    def analyze(self, resume_text: str, preferences: dict | None = None) -> AnalysisResult:
        preferences = preferences or {}
        if self._ai_configured():
            try:
                return self._call_ai(resume_text, preferences)
            except Exception:
                logger.exception("AI resume analysis failed; using local fallback")
        return self._local_fallback(resume_text, preferences)

    def _ai_configured(self) -> bool:
        return openrouter_configured()

    def _load_prompt(self, resume_text: str, preferences: dict) -> str:
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
        return template.format(
            resume_text=resume_text[:12000],
            target_roles=", ".join(preferences.get("target_roles", [])) or "Not specified",
            target_locations=", ".join(preferences.get("target_locations", [])) or "Not specified",
            remote_preference=preferences.get("remote_preference", "flexible"),
            career_goals=preferences.get("career_goals", "") or "Not specified",
            skills=", ".join(preferences.get("skills", [])) or "Not specified",
        )

    def _call_ai(self, resume_text: str, preferences: dict) -> AnalysisResult:
        prompt = self._load_prompt(resume_text, preferences)
        content = invoke_openrouter(
            prompt,
            model=self.model,
            temperature=0.3,
            timeout=60,
            response_format={"type": "json_object"},
        )
        parsed = parse_json_content(content)
        return AnalysisResult(
            model_name=self.model,
            raw_summary=parsed.get("summary", ""),
            health_score=self._clamp_score(parsed.get("health_score", 0)),
            ats_score=self._clamp_score(parsed.get("ats_score", 0)),
            strengths=self._as_str_list(parsed.get("strengths")),
            weaknesses=self._as_str_list(parsed.get("weaknesses")),
            missing_keywords=self._as_str_list(parsed.get("missing_keywords")),
            improvement_suggestions=self._as_str_list(parsed.get("improvement_suggestions")),
            extracted_skills=self._as_str_list(parsed.get("extracted_skills")),
            used_fallback=False,
        )

    def _parse_json_response(self, content: str) -> dict:
        content = content.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if fence_match:
            content = fence_match.group(1).strip()
        return json.loads(content)

    def _local_fallback(self, resume_text: str, preferences: dict) -> AnalysisResult:
        words = resume_text.split()
        word_count = len(words)
        has_email = "@" in resume_text
        has_phone = bool(re.search(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", resume_text))
        sections = sum(
            1
            for keyword in ("experience", "education", "skills", "summary", "projects")
            if keyword.lower() in resume_text.lower()
        )

        health_score = min(100, 30 + sections * 12 + (10 if has_email else 0) + (5 if has_phone else 0))
        ats_score = min(100, 25 + sections * 15 + min(20, word_count // 50))

        skills_found = self._extract_skills_heuristic(resume_text)
        target_roles = preferences.get("target_roles", [])
        missing = [role for role in target_roles[:3] if role.lower() not in resume_text.lower()]

        return AnalysisResult(
            model_name="local-fallback",
            raw_summary=(
                f"Resume contains approximately {word_count} words with "
                f"{sections} recognizable sections. "
                "This is a deterministic local analysis — configure OPENAI_API_KEY and "
                "OPENROUTER_BASE_URL for AI-powered insights."
            ),
            health_score=health_score,
            ats_score=ats_score,
            strengths=[
                "Resume text was successfully extracted",
                f"Contains {sections} standard resume sections" if sections else "Readable content detected",
                "Contact information present" if has_email else "Structured text content",
            ],
            weaknesses=[
                "AI analysis unavailable — using heuristic scoring",
                "Quantified achievements may be missing" if "%" not in resume_text else "Review achievement formatting",
                "Keyword alignment with target roles needs review" if missing else "Consider adding more role-specific keywords",
            ],
            missing_keywords=missing or ["Configure AI for personalized keyword analysis"],
            improvement_suggestions=[
                "Add measurable outcomes to each role (metrics, percentages, scale)",
                "Align skills section with target role keywords",
                "Ensure contact information is clearly formatted at the top",
                "Configure OpenRouter for personalized AI analysis",
            ],
            extracted_skills=skills_found,
            used_fallback=True,
        )

    def _extract_skills_heuristic(self, text: str) -> list[str]:
        common_skills = [
            "Python", "JavaScript", "TypeScript", "Java", "React", "Django",
            "SQL", "AWS", "Docker", "Kubernetes", "Git", "REST", "API",
            "Leadership", "Communication", "Agile", "CI/CD", "PostgreSQL",
        ]
        found = [skill for skill in common_skills if skill.lower() in text.lower()]
        return found[:10]

    @staticmethod
    def _clamp_score(value) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, score))

    @staticmethod
    def _as_str_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, str) and value:
            return [value]
        return []
