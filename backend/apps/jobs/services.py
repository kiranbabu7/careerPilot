"""Job search orchestration — discovery, enrichment, dedupe, persistence."""

import logging
from typing import Any

from apps.jobs.models import OpportunityStatus
from apps.jobs.repositories import JobRepository, OpportunityRepository
from apps.providers.jobs.apify import ApifyJobsProvider
from apps.providers.jobs.base import JobListing
from apps.providers.jobs.normalization import build_dedupe_key, parse_posted_at
from apps.providers.jobs.tavily_research import TavilyCompanyResearchProvider

logger = logging.getLogger(__name__)


class JobSearchService:
    def __init__(
        self,
        job_repo: JobRepository | None = None,
        opportunity_repo: OpportunityRepository | None = None,
        apify_provider: ApifyJobsProvider | None = None,
        tavily_provider: TavilyCompanyResearchProvider | None = None,
    ):
        self.job_repo = job_repo or JobRepository()
        self.opportunity_repo = opportunity_repo or OpportunityRepository()
        self.apify_provider = apify_provider or ApifyJobsProvider()
        self.tavily_provider = tavily_provider or TavilyCompanyResearchProvider()

    def build_search_query(self, context: dict) -> str:
        goal = context.get("goal", "").strip()
        prefs = context.get("preferences", {})
        roles = prefs.get("target_roles", [])
        skills = prefs.get("skills", [])

        parts: list[str] = []
        if roles:
            parts.append(roles[0])
        elif goal:
            parts.append(goal[:120])
        if skills:
            parts.extend(skills[:3])
        return " ".join(parts).strip() or goal or "software engineer"

    def build_search_location(self, context: dict) -> str:
        locations = context.get("preferences", {}).get("target_locations", [])
        if locations:
            return locations[0]
        return ""

    def search(
        self,
        user,
        workflow,
        context: dict,
    ) -> dict[str, Any]:
        query = self.build_search_query(context)
        location = self.build_search_location(context)
        provider_summary: dict[str, Any] = {
            "query": query,
            "location": location,
            "providers": {},
            "errors": [],
        }

        listings: list[JobListing] = []
        apify_errors: list[str] = []

        try:
            listings = self.apify_provider.search_jobs(
                query, location=location, max_items=None
            )
            provider_summary["providers"]["apify"] = {
                "status": "completed",
                "count": len(listings),
                "actor_ids": self.apify_provider.actor_ids,
            }
        except Exception as exc:
            logger.exception("Apify job search failed")
            apify_errors.append(str(exc))
            provider_summary["providers"]["apify"] = {
                "status": "failed",
                "count": 0,
                "error": str(exc),
            }
            provider_summary["errors"].append(f"apify: {exc}")

        company_research: dict[str, dict[str, Any]] = {}
        try:
            company_research = self.tavily_provider.enrich_jobs(listings)
            enriched_count = sum(
                1 for v in company_research.values() if v.get("available")
            )
            provider_summary["providers"]["tavily_research"] = {
                "status": "completed",
                "companies_enriched": enriched_count,
            }
        except Exception as exc:
            logger.exception("Tavily enrichment failed")
            provider_summary["providers"]["tavily_research"] = {
                "status": "failed",
                "error": str(exc),
            }
            provider_summary["errors"].append(f"tavily: {exc}")

        opportunities = self._persist_listings(
            user,
            workflow,
            listings,
            company_research,
            context,
        )

        return {
            "query": query,
            "location": location,
            "discovered_count": len(opportunities),
            "total_listings": len(listings),
            "opportunities": opportunities,
            "provider_summary": provider_summary,
            "errors": provider_summary["errors"],
        }

    def _persist_listings(
        self,
        user,
        workflow,
        listings: list[JobListing],
        company_research: dict[str, dict[str, Any]],
        context: dict,
    ) -> list:
        opportunities = []
        seen_dedupe: set[str] = set()

        for listing in listings:
            dedupe_key = build_dedupe_key(listing)
            if dedupe_key in seen_dedupe:
                continue
            seen_dedupe.add(dedupe_key)

            job = self.job_repo.get_by_dedupe_key(dedupe_key)
            if job is None and listing.external_id:
                job = self.job_repo.get_by_source_and_external_id(
                    listing.source, listing.external_id
                )

            research = company_research.get(listing.company, {})

            if job is None:
                job = self.job_repo.create(
                    external_id=listing.external_id,
                    source=listing.source,
                    title=listing.title,
                    company=listing.company,
                    location=listing.location,
                    is_remote=listing.is_remote,
                    salary_min=listing.salary_min,
                    salary_max=listing.salary_max,
                    salary_currency=listing.salary_currency or "",
                    description=listing.description,
                    apply_url=listing.url,
                    posted_at=parse_posted_at(listing.posted_at),
                    raw_payload=listing.raw_payload,
                    dedupe_key=dedupe_key,
                    company_research=research,
                )
            elif research.get("available"):
                job = self.job_repo.update(job, company_research=research)

            existing = self.opportunity_repo.get_for_user_job_workflow(
                user, job, workflow
            )
            if existing:
                opportunities.append(existing)
                continue

            match_context = self._build_match_context(listing, context)
            opportunity = self.opportunity_repo.create(
                user=user,
                job=job,
                workflow_execution=workflow,
                status=OpportunityStatus.DISCOVERED,
                source_agent="job_search",
                match_context=match_context,
            )
            opportunities.append(opportunity)

        return opportunities

    def _build_match_context(self, listing: JobListing, context: dict) -> str:
        prefs = context.get("preferences", {})
        roles = prefs.get("target_roles", [])
        skills = prefs.get("skills", [])
        goal = context.get("goal", "")

        parts: list[str] = []
        if roles and any(r.lower() in listing.title.lower() for r in roles):
            parts.append(f"Matches target role: {roles[0]}.")
        elif goal:
            parts.append(f"Relevant to your goal: {goal[:100]}.")

        matched_skills = [
            s for s in skills if s.lower() in listing.description.lower()
        ]
        if matched_skills:
            parts.append(f"Skills overlap: {', '.join(matched_skills[:5])}.")
        if listing.is_remote:
            parts.append("Remote-friendly role.")
        if listing.location:
            parts.append(f"Location: {listing.location}.")

        if not parts:
            parts.append(f"Discovered via {listing.source} for your career search.")
        return " ".join(parts)
