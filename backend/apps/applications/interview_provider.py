"""Interview prep LLM provider with deterministic fallback."""

import json
import logging
import re
from dataclasses import dataclass

from django.conf import settings

from apps.providers.llm.json_output import parse_json_content
from apps.providers.llm.openrouter_chat import invoke_openrouter, openrouter_configured
from apps.resumes.providers import RESUME_ANALYSIS_MODEL

logger = logging.getLogger(__name__)

INTERVIEW_PLAN_SECTIONS = (
    "prep_roadmap",
    "likely_questions",
    "system_design_topics",
    "company_talking_points",
    "resume_stories",
    "gaps_to_practice",
    "day_by_day_checklist",
)


@dataclass
class InterviewPlanGenerationResult:
    content: dict
    markdown: str
    model_name: str
    used_fallback: bool = False


class InterviewPrepProvider:
    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "").rstrip("/")
        self.model = RESUME_ANALYSIS_MODEL

    def generate(self, prompt_text: str) -> InterviewPlanGenerationResult:
        if self._ai_configured():
            try:
                return self._call_ai(prompt_text)
            except Exception:
                logger.exception(
                    "AI interview prep generation failed; using local fallback"
                )
        return self._local_fallback(prompt_text)

    def _ai_configured(self) -> bool:
        return openrouter_configured()

    def _call_ai(self, prompt_text: str) -> InterviewPlanGenerationResult:
        raw = invoke_openrouter(
            prompt_text,
            model=self.model,
            temperature=0.4,
            timeout=120,
        )
        content = self._parse_json(raw)
        markdown = self._content_to_markdown(content)
        return InterviewPlanGenerationResult(
            content=content,
            markdown=markdown,
            model_name=self.model,
            used_fallback=False,
        )

    def _local_fallback(self, prompt_text: str) -> InterviewPlanGenerationResult:
        job_title = self._extract_field(prompt_text, "Title:")
        job_company = self._extract_field(prompt_text, "Company:")
        application_stage = self._extract_field(prompt_text, "Application stage:")
        evaluation = self._extract_section(prompt_text, "## Match evaluation")
        gaps = self._extract_gaps(evaluation)

        content = {
            "prep_roadmap": [
                f"Review the {job_title or 'role'} requirements and map them to your experience.",
                f"Research {job_company or 'the company'} recent news, product direction, and culture.",
                "Prepare 3–5 STAR stories aligned with the job description.",
                "Practice explaining your strongest technical projects end-to-end.",
                "Prepare thoughtful questions for the interviewer about team and roadmap.",
            ],
            "likely_questions": [
                f"Why are you interested in the {job_title or 'role'} at {job_company or 'this company'}?",
                "Walk me through a challenging project and your specific contributions.",
                "Describe a time you had to make a trade-off under deadline pressure.",
                "How do you approach debugging production issues?",
                "What are you looking for in your next role?",
            ],
            "system_design_topics": [
                "Scalability patterns for high-traffic APIs",
                "Database indexing, caching, and consistency trade-offs",
                "Service boundaries and event-driven architecture basics",
            ],
            "company_talking_points": [
                f"Connect your experience to {job_company or 'the company'} mission and product.",
                "Reference company research snippets from your discovery workflow.",
                "Highlight culture fit and remote collaboration experience if relevant.",
            ],
            "resume_stories": [
                "Lead with a project that best matches the top job requirements.",
                "Quantify impact (latency, revenue, users, cost savings) where possible.",
                "Explain your role clearly versus team contributions.",
            ],
            "gaps_to_practice": gaps
            or [
                "Review any skill gaps noted in the match evaluation.",
                "Prepare honest framing for areas where you are still growing.",
            ],
            "day_by_day_checklist": [
                {"day": 1, "tasks": ["Re-read job description", "Review company research"]},
                {
                    "day": 2,
                    "tasks": ["Draft STAR stories", "Practice aloud for 30 minutes"],
                },
                {
                    "day": 3,
                    "tasks": [
                        "Mock technical questions",
                        "Prepare questions for interviewer",
                    ],
                },
            ],
        }
        if application_stage:
            content["application_stage"] = application_stage

        markdown = self._content_to_markdown(content)
        markdown += (
            "\n\n---\n*Deterministic local plan — configure OPENAI_API_KEY and "
            "OPENROUTER_BASE_URL for AI-powered interview prep.*"
        )
        return InterviewPlanGenerationResult(
            content=content,
            markdown=markdown,
            model_name="local-fallback",
            used_fallback=True,
        )

    def _parse_json(self, raw: str) -> dict:
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        text = fence_match.group(1).strip() if fence_match else raw
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return self._normalize_content(parsed)
        except json.JSONDecodeError:
            pass
        return self._local_fallback(raw).content

    def _normalize_content(self, content: dict) -> dict:
        normalized = {}
        for key in INTERVIEW_PLAN_SECTIONS:
            value = content.get(key)
            if value is None:
                normalized[key] = []
            else:
                normalized[key] = value
        return normalized

    def _content_to_markdown(self, content: dict) -> str:
        sections = [
            ("Prep roadmap", content.get("prep_roadmap", [])),
            ("Likely questions", content.get("likely_questions", [])),
            ("System design topics", content.get("system_design_topics", [])),
            ("Company talking points", content.get("company_talking_points", [])),
            ("Resume stories", content.get("resume_stories", [])),
            ("Gaps to practice", content.get("gaps_to_practice", [])),
        ]
        lines: list[str] = ["# Interview Prep Plan", ""]
        for title, items in sections:
            lines.append(f"## {title}")
            lines.append("")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        lines.append(f"- Day {item.get('day', '?')}: {', '.join(item.get('tasks', []))}")
                    else:
                        lines.append(f"- {item}")
            lines.append("")

        checklist = content.get("day_by_day_checklist", [])
        if checklist:
            lines.append("## Day-by-day checklist")
            lines.append("")
            for entry in checklist:
                if isinstance(entry, dict):
                    day = entry.get("day", "?")
                    tasks = entry.get("tasks", [])
                    lines.append(f"### Day {day}")
                    for task in tasks:
                        lines.append(f"- {task}")
                    lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_field(text: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}\s*(.+)", text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_section(text: str, heading: str) -> str:
        pattern = rf"{re.escape(heading)}\s*\n+([\s\S]*?)(?:\n## |\Z)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_gaps(evaluation_text: str) -> list[str]:
        match = re.search(r"Gaps:\s*(.+)", evaluation_text)
        if not match:
            return []
        return [g.strip() for g in match.group(1).split(";") if g.strip()]
