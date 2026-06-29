"""Tavily company research and news enrichment — not primary job search."""

import logging
import time
from typing import Any

from django.conf import settings

from apps.providers.jobs.company_research_synthesis import (
    CompanyResearchSynthesisProvider,
    build_fallback_research_queries,
    build_research_payload,
    build_research_queries,
    collect_snippets,
    normalize_sections,
)

logger = logging.getLogger(__name__)

_RATE_LIMIT_MARKERS = ("429", "rate limit", "too many requests")
_AUTH_ERROR_MARKERS = (
    "401",
    "403",
    "unauthorized",
    "forbidden",
    "invalid api key",
    "authentication",
    "invalid key",
)
_NETWORK_ERROR_MARKERS = ("timeout", "timed out", "connection", "network", "dns")


def classify_tavily_errors(errors: list[str]) -> tuple[str, str]:
    """Map Tavily exception messages to a reason code and primary error text."""
    if not errors:
        return "no_results", "All Tavily searches returned no data"

    combined = " ".join(errors).lower()
    if any(marker in combined for marker in _AUTH_ERROR_MARKERS):
        return "auth_error", errors[0]
    if any(marker in combined for marker in _RATE_LIMIT_MARKERS):
        return "rate_limited", errors[0]
    if any(marker in combined for marker in _NETWORK_ERROR_MARKERS):
        return "network_error", errors[0]
    return "request_failed", errors[0]


class TavilyCompanyResearchProvider:
    """Enriches discovered jobs with company research and recent news snippets."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: Any | None = None,
        synthesis_provider: CompanyResearchSynthesisProvider | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.TAVILY_API_KEY
        self._client = client
        self.synthesis_provider = (
            synthesis_provider or CompanyResearchSynthesisProvider()
        )

    @property
    def provider_name(self) -> str:
        return "tavily_research"

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        from tavily import TavilyClient

        return TavilyClient(self.api_key)

    def _run_searches(
        self,
        client: Any,
        *,
        company: str,
        queries: list[dict[str, str]],
        max_results: int,
        search_depth: str = "advanced",
        errors: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        categorized_searches: list[dict[str, Any]] = []
        collected_errors = errors if errors is not None else []

        for spec in queries:
            try:
                data = client.search(
                    query=spec["query"],
                    search_depth=search_depth,
                    max_results=max_results,
                    include_answer=True,
                )
                categorized_searches.append(
                    {
                        "category": spec["category"],
                        "query": spec["query"],
                        "data": data,
                    }
                )
            except Exception as exc:
                error_text = str(exc)
                logger.warning(
                    "Tavily research failed for %s (%s, depth=%s): %s",
                    company,
                    spec["category"],
                    search_depth,
                    error_text,
                )
                collected_errors.append(error_text)
                if any(marker in error_text.lower() for marker in _RATE_LIMIT_MARKERS):
                    time.sleep(0.5)

        return categorized_searches

    def enrich_company(
        self,
        company: str,
        *,
        job_title: str = "",
        max_results: int = 2,
    ) -> dict[str, Any]:
        if not self.api_key:
            logger.debug("Tavily API key not configured; skipping company research")
            return {"available": False, "reason": "not_configured"}

        if not company.strip():
            return {"available": False, "reason": "empty_company"}

        client = self._get_client()
        if client is None:
            return {"available": False, "reason": "not_configured"}

        errors: list[str] = []
        queries = build_research_queries(company, job_title)
        categorized_searches = self._run_searches(
            client,
            company=company,
            queries=queries,
            max_results=max_results,
            search_depth="advanced",
            errors=errors,
        )

        if not categorized_searches:
            fallback_queries = build_fallback_research_queries(company)
            logger.info(
                "Primary Tavily searches failed for %s; trying %s fallback queries",
                company,
                len(fallback_queries),
            )
            categorized_searches = self._run_searches(
                client,
                company=company,
                queries=fallback_queries,
                max_results=max_results,
                search_depth="basic",
                errors=errors,
            )

        if not categorized_searches:
            reason, primary_error = classify_tavily_errors(errors)
            logger.error(
                "Company research unavailable for %s: reason=%s error=%s failures=%s",
                company,
                reason,
                primary_error,
                errors,
            )
            return {
                "available": False,
                "reason": reason,
                "error": primary_error,
                "errors": errors,
                "company": company.strip(),
            }

        synthesis = self.synthesis_provider.synthesize(
            company=company.strip(),
            job_title=job_title,
            categorized_searches=categorized_searches,
        )
        payload = build_research_payload(
            company=company.strip(),
            categorized_searches=categorized_searches,
            sections=synthesis.sections,
        )
        if not payload.get("available"):
            payload["reason"] = "no_content"
            payload["error"] = "Tavily returned results but no usable company content."
        return payload

    @staticmethod
    def _map_search_response(
        data: dict[str, Any],
        *,
        company: str,
        max_results: int,
    ) -> dict[str, Any]:
        """Legacy single-search mapper kept for backward-compatible tests."""
        snippets = collect_snippets(
            [{"category": "general", "data": data}],
            max_per_category=max_results,
            max_total=max_results,
        )
        sections = normalize_sections(
            {
                "summary": data.get("answer", ""),
                "what_they_do": "",
                "recent_news": "",
                "funding": "",
                "hiring_signals": "",
            }
        )
        return build_research_payload(
            company=company,
            categorized_searches=[{"category": "general", "data": data}],
            sections=sections,
        )

    def enrich_jobs(
        self,
        listings: list,
        *,
        max_companies: int = 10,
    ) -> dict[str, dict[str, Any]]:
        """Return company-name -> research dict for unique companies."""
        if not self.api_key:
            return {}

        seen: set[str] = set()
        enrichment: dict[str, dict[str, Any]] = {}

        for listing in listings:
            company = getattr(listing, "company", "") or ""
            normalized = company.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            if len(seen) > max_companies:
                break
            title = getattr(listing, "title", "") or ""
            enrichment[company] = self.enrich_company(company, job_title=title)

        return enrichment
