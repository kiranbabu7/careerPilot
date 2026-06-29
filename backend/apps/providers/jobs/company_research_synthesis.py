"""Synthesize multi-query Tavily results into structured company research."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.prompts.services import PromptService
from apps.providers.llm.json_output import parse_json_content
from apps.providers.llm.openrouter_chat import invoke_openrouter, openrouter_configured
from apps.resumes.providers import RESUME_ANALYSIS_MODEL

logger = logging.getLogger(__name__)

COMPANY_RESEARCH_PROMPT_NAME = "company_research"

RESEARCH_SECTIONS = (
    "summary",
    "what_they_do",
    "recent_news",
    "funding",
    "hiring_signals",
)


@dataclass
class CompanyResearchSynthesisResult:
    sections: dict[str, str]
    model_name: str
    used_fallback: bool = False


class CompanyResearchSynthesisProvider:
    def __init__(self, prompt_service: PromptService | None = None):
        self.prompt_service = prompt_service or PromptService()
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "").rstrip("/")
        self.model = RESUME_ANALYSIS_MODEL

    def synthesize(
        self,
        *,
        company: str,
        job_title: str,
        categorized_searches: list[dict[str, Any]],
    ) -> CompanyResearchSynthesisResult:
        if self._ai_configured():
            try:
                return self._call_ai(
                    company=company,
                    job_title=job_title,
                    categorized_searches=categorized_searches,
                )
            except Exception:
                logger.exception(
                    "AI company research synthesis failed; using rule-based fallback"
                )
        return self._rule_based_fallback(
            company=company,
            categorized_searches=categorized_searches,
        )

    def _ai_configured(self) -> bool:
        return openrouter_configured()

    def _call_ai(
        self,
        *,
        company: str,
        job_title: str,
        categorized_searches: list[dict[str, Any]],
    ) -> CompanyResearchSynthesisResult:
        rendered = self.prompt_service.render(
            COMPANY_RESEARCH_PROMPT_NAME,
            {
                "company": company,
                "job_title": job_title or "Not specified",
                "search_findings": format_search_findings(categorized_searches),
            },
        )
        raw = invoke_openrouter(
            rendered["rendered_text"],
            model=self.model,
            temperature=0.3,
            timeout=90,
        )
        sections = self._parse_json_sections(raw)
        return CompanyResearchSynthesisResult(
            sections=sections,
            model_name=self.model,
            used_fallback=False,
        )

    def _parse_json_sections(self, raw: str) -> dict[str, str]:
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        text = fence_match.group(1).strip() if fence_match else raw
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return normalize_sections(parsed)
        except json.JSONDecodeError:
            pass
        return {}

    def _rule_based_fallback(
        self,
        *,
        company: str,
        categorized_searches: list[dict[str, Any]],
    ) -> CompanyResearchSynthesisResult:
        by_category: dict[str, str] = {}
        for item in categorized_searches:
            category = item.get("category", "")
            data = item.get("data") or {}
            answer = (data.get("answer") or "").strip()
            if answer:
                by_category[category] = answer

        overview = by_category.get("overview", "")
        products = by_category.get("products", "")
        if overview and products:
            what_they_do = f"{overview} {products}".strip()
        else:
            what_they_do = products or overview

        summary_parts = [p for p in (overview, by_category.get("news", "")) if p]
        summary = " ".join(summary_parts[:2])[:600] if summary_parts else what_they_do[:400]

        sections = normalize_sections(
            {
                "summary": summary,
                "what_they_do": what_they_do,
                "recent_news": by_category.get("news", ""),
                "funding": by_category.get("funding", ""),
                "hiring_signals": by_category.get("hiring", ""),
            }
        )
        return CompanyResearchSynthesisResult(
            sections=sections,
            model_name="rule-based-fallback",
            used_fallback=True,
        )


def build_fallback_research_queries(company: str) -> list[dict[str, str]]:
    """Simpler queries when categorized advanced searches all fail."""
    company = company.strip()
    if not company:
        return []

    return [
        {"category": "general", "query": f'"{company}" company'},
        {"category": "general", "query": f"{company} official website about"},
    ]


def build_research_queries(company: str, job_title: str = "") -> list[dict[str, str]]:
    """Return categorized Tavily queries — business-first, hiring secondary."""
    company = company.strip()
    if not company:
        return []

    title = job_title.strip()
    hiring_query = (
        f"{company} hiring {title} careers workplace culture"
        if title
        else f"{company} hiring careers workplace culture jobs"
    )

    return [
        {"category": "overview", "query": f"{company} company overview what does the company do"},
        {
            "category": "products",
            "query": f"{company} products services solutions industry market",
        },
        {
            "category": "funding",
            "query": f"{company} funding investors valuation acquisition IPO",
        },
        {
            "category": "news",
            "query": f"{company} recent news announcements events partnerships",
        },
        {"category": "hiring", "query": hiring_query},
    ]


def format_search_findings(categorized_searches: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in categorized_searches:
        category = item.get("category", "general")
        data = item.get("data") or {}
        lines.append(f"### {category.replace('_', ' ').title()}")
        answer = (data.get("answer") or "").strip()
        if answer:
            lines.append(answer)
        for result in (data.get("results") or [])[:3]:
            title = result.get("title", "")
            snippet = (result.get("content") or "")[:400]
            if title or snippet:
                lines.append(f"- {title}: {snippet}".strip())
        lines.append("")
    return "\n".join(lines).strip()


def collect_snippets(
    categorized_searches: list[dict[str, Any]],
    *,
    max_per_category: int = 2,
    max_total: int = 8,
) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in categorized_searches:
        category = item.get("category", "")
        data = item.get("data") or {}
        for result in (data.get("results") or [])[:max_per_category]:
            url = result.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            snippets.append(
                {
                    "title": result.get("title", ""),
                    "url": url,
                    "snippet": (result.get("content") or "")[:500],
                    "category": category,
                }
            )
            if len(snippets) >= max_total:
                return snippets
    return snippets


def normalize_sections(sections: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key in RESEARCH_SECTIONS:
        value = sections.get(key, "")
        normalized[key] = str(value).strip() if value else ""
    return normalized


def build_research_payload(
    *,
    company: str,
    categorized_searches: list[dict[str, Any]],
    sections: dict[str, str],
) -> dict[str, Any]:
    snippets = collect_snippets(categorized_searches)
    has_content = any(sections.values()) or bool(snippets)
    return {
        "available": has_content,
        "company": company,
        "summary": sections.get("summary", ""),
        "what_they_do": sections.get("what_they_do", ""),
        "recent_news": sections.get("recent_news", ""),
        "funding": sections.get("funding", ""),
        "hiring_signals": sections.get("hiring_signals", ""),
        "snippets": snippets,
    }
