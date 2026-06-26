"""Tavily company research and news enrichment — not primary job search."""

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyCompanyResearchProvider:
    """Enriches discovered jobs with company research and recent news snippets."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.TAVILY_API_KEY
        self.session = session or requests.Session()

    @property
    def provider_name(self) -> str:
        return "tavily_research"

    def enrich_company(
        self,
        company: str,
        *,
        job_title: str = "",
        max_results: int = 3,
    ) -> dict[str, Any]:
        if not self.api_key:
            logger.debug("Tavily API key not configured; skipping company research")
            return {"available": False, "reason": "not_configured"}

        if not company.strip():
            return {"available": False, "reason": "empty_company"}

        query_parts = [company.strip()]
        if job_title:
            query_parts.append(job_title.strip())
        query = " ".join(query_parts) + " company hiring news"

        try:
            response = self.session.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": True,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning("Tavily research failed for %s: %s", company, exc)
            return {
                "available": False,
                "reason": "request_failed",
                "error": str(exc),
            }

        snippets = []
        for result in data.get("results", [])[:max_results]:
            snippets.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", "")[:500],
                }
            )

        return {
            "available": True,
            "company": company,
            "summary": data.get("answer", ""),
            "snippets": snippets,
        }

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
