"""Job search orchestration — discovery, enrichment, dedupe, persistence."""

import logging
from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.jobs.models import OpportunityStatus
from apps.jobs.repositories import JobRepository, OpportunityRepository
from apps.providers.jobs.apify import (
    ApifyJobsProvider,
    build_linkedin_search_urls,
    resolve_linkedin_location,
    resolve_split_country,
)
from apps.providers.jobs.base import JobListing
from apps.providers.jobs.normalization import build_dedupe_key, parse_posted_at
from apps.providers.jobs.tavily_research import TavilyCompanyResearchProvider

logger = logging.getLogger(__name__)

MAX_SEARCH_QUERY_LEN = 80
MAX_ROLE_KEYWORDS = 2


def _is_new_listing(listing: JobListing, posted_since: datetime) -> bool:
    """Return True when a listing was posted on or after the cutoff."""
    if not listing.posted_at:
        return False

    cutoff = posted_since
    if timezone.is_naive(cutoff):
        cutoff = timezone.make_aware(cutoff, timezone.get_current_timezone())

    posted_value = listing.posted_at.strip()
    # LinkedIn/Apify often return date-only values (YYYY-MM-DD). Comparing at
    # midnight would exclude same-day listings when cutoff is later that day.
    if len(posted_value) == 10:
        parsed = parse_posted_at(posted_value)
        if parsed is None:
            return False
        return parsed.date() >= cutoff.date()

    parsed = parse_posted_at(listing.posted_at)
    if parsed is None:
        return False
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed >= cutoff


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

    def _parse_preferences(self, context: dict) -> dict[str, Any]:
        """Extract shared search fields from workflow context preferences."""
        prefs = context.get("preferences", {})
        planner_constraints = context.get("planner_constraints") or {}
        search_overrides = context.get("search_overrides") or {}
        roles = [r.strip() for r in prefs.get("target_roles", []) if r and r.strip()]
        skills = [s.strip() for s in prefs.get("skills", []) if s and s.strip()]
        remote_preference = (prefs.get("remote_preference") or "flexible").lower()
        locations = [
            loc.strip() for loc in prefs.get("target_locations", []) if loc and loc.strip()
        ]

        constraint_role = (planner_constraints.get("role") or "").strip()
        if constraint_role and constraint_role not in roles:
            roles = [constraint_role, *roles]

        if planner_constraints.get("remote_preference"):
            remote_preference = str(planner_constraints["remote_preference"]).lower()
        elif (planner_constraints.get("location") or "").lower() == "remote":
            remote_preference = "remote"

        constraint_location = (planner_constraints.get("location") or "").strip()
        if constraint_location and constraint_location.lower() != "remote":
            if constraint_location not in locations:
                locations = [constraint_location, *locations]

        override_query = (search_overrides.get("query") or "").strip()
        override_location = (search_overrides.get("location") or "").strip()
        if search_overrides.get("remote_preference"):
            remote_preference = str(search_overrides["remote_preference"]).lower()

        if override_query:
            query = override_query[:MAX_SEARCH_QUERY_LEN]
        elif not roles:
            goal = context.get("goal", "").strip()
            career_goals = (prefs.get("career_goals") or "").strip()
            roles = [goal or career_goals or "software engineer"]
            query = roles[0][:MAX_SEARCH_QUERY_LEN]
        elif roles:
            query = " ".join(roles[:MAX_ROLE_KEYWORDS])[:MAX_SEARCH_QUERY_LEN]
        else:
            goal = context.get("goal", "").strip()
            career_goals = (prefs.get("career_goals") or "").strip()
            query = (goal or career_goals or "software engineer")[:MAX_SEARCH_QUERY_LEN]

        if override_location:
            locations = [override_location]

        company_stage = (planner_constraints.get("company_stage") or "").strip()
        if company_stage and "startup" in company_stage.lower():
            if "startup" not in query.lower():
                query = f"{query} startup".strip()[:MAX_SEARCH_QUERY_LEN]

        split_country = resolve_split_country(locations, remote_preference)
        url_location = resolve_linkedin_location(locations, remote_preference)

        if locations:
            summary_location = locations[0]
        elif remote_preference == "remote":
            summary_location = "Remote"
        else:
            summary_location = ""

        max_results = search_overrides.get("max_results")
        if max_results is not None:
            try:
                max_results = max(1, min(int(max_results), 100))
            except (TypeError, ValueError):
                max_results = None

        return {
            "roles": roles,
            "skills": skills,
            "remote_preference": remote_preference,
            "query": query,
            "summary_location": summary_location,
            "url_location": url_location,
            "split_country": split_country,
            "max_results": max_results,
            "planner_constraints": planner_constraints,
        }

    def build_linkedin_search_urls(
        self, context: dict, *, posted_since: datetime | None = None
    ) -> list[str]:
        """Build LinkedIn job search URLs for the curious_coder Apify actor."""
        prefs = self._parse_preferences(context)
        return build_linkedin_search_urls(
            roles=prefs["roles"],
            skills=prefs["skills"],
            location=prefs["url_location"],
            remote_preference=prefs["remote_preference"],
            posted_since=posted_since,
        )

    def search(
        self,
        user,
        workflow,
        context: dict,
        *,
        posted_since: datetime | None = None,
    ) -> dict[str, Any]:
        prefs = self._parse_preferences(context)
        query = prefs["query"]
        location = prefs["summary_location"]
        split_country = prefs["split_country"]
        linkedin_urls = self.build_linkedin_search_urls(context, posted_since=posted_since)
        apify_configured = bool(
            self.apify_provider.api_token and self.apify_provider.actor_ids
        )
        provider_summary: dict[str, Any] = {
            "query": query,
            "location": location,
            "linkedin_urls": linkedin_urls,
            "providers": {},
            "errors": [],
        }

        listings: list[JobListing] = []

        if not apify_configured:
            provider_summary["providers"]["apify"] = {
                "status": "skipped",
                "count": 0,
                "configured": False,
            }
        else:
            try:
                listings = self.apify_provider.search_jobs(
                    query,
                    location=location,
                    urls=linkedin_urls,
                    split_country=split_country,
                )
                raw_errors = getattr(self.apify_provider, "last_search_errors", [])
                apify_errors = raw_errors if isinstance(raw_errors, list) else []
                apify_status = "completed"
                apify_entry: dict[str, Any] = {
                    "status": apify_status,
                    "count": len(listings),
                    "configured": True,
                }
                if apify_errors:
                    provider_summary["errors"].extend(
                        f"apify: {error}" for error in apify_errors
                    )
                    if listings:
                        apify_status = "partial"
                    else:
                        apify_status = "failed"
                    apify_entry["status"] = apify_status
                    apify_entry["error"] = apify_errors[0]
                provider_summary["providers"]["apify"] = apify_entry
            except Exception as exc:
                logger.exception("Apify job search failed")
                provider_summary["providers"]["apify"] = {
                    "status": "failed",
                    "count": 0,
                    "configured": True,
                    "error": str(exc),
                }
                provider_summary["errors"].append(f"apify: {exc}")

        # Company research is deferred until after initial job evaluation so
        # poorly matched roles are not enriched during discovery.
        company_research: dict[str, dict[str, Any]] = {}
        provider_summary["providers"]["tavily_research"] = {
            "status": "deferred",
            "companies_enriched": 0,
            "reason": "Runs after initial fit screening for viable matches.",
        }

        max_results = prefs.get("max_results")
        if max_results is not None and len(listings) > max_results:
            listings = listings[:max_results]

        if posted_since is not None:
            listings = [listing for listing in listings if _is_new_listing(listing, posted_since)]

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
            "new_count": len(opportunities),
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
        """Persist listings; returns only newly created opportunities for this user."""
        new_opportunities = []
        reevaluate: list = []
        seen_dedupe: set[str] = set()

        for listing in listings:
            dedupe_key = build_dedupe_key(listing)
            if dedupe_key in seen_dedupe:
                continue
            seen_dedupe.add(dedupe_key)

            job = self.job_repo.find_existing(listing)
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
            else:
                updates: dict[str, Any] = {}
                if job.dedupe_key != dedupe_key:
                    updates["dedupe_key"] = dedupe_key
                if listing.external_id and not job.external_id:
                    updates["external_id"] = listing.external_id
                if listing.url and not job.apply_url:
                    updates["apply_url"] = listing.url
                if research.get("available"):
                    updates["company_research"] = research
                if updates:
                    job = self.job_repo.update(job, **updates)

            existing = self.opportunity_repo.get_for_user_job(user, job)
            if existing is None:
                existing = self.opportunity_repo.get_for_user_equivalent_job(
                    user,
                    listing.title,
                    listing.company,
                    listing.location or "",
                )
                if existing is not None and existing.job_id != job.id:
                    job = existing.job
            if existing:
                if (
                    existing.match_score is None
                    and existing.workflow_execution_id != workflow.id
                ):
                    existing.workflow_execution = workflow
                    existing.save(update_fields=["workflow_execution", "updated_at"])
                if research.get("available") and existing.match_score is not None:
                    existing.job = job
                    reevaluate.append(existing)
                continue

            match_context = self._build_match_context(listing, context)
            opportunity, _created = self.opportunity_repo.get_or_create_for_user_job(
                user,
                job,
                workflow=workflow,
                defaults={
                    "status": OpportunityStatus.DISCOVERED,
                    "source_agent": "job_search",
                    "match_context": match_context,
                },
            )
            new_opportunities.append(opportunity)

        if reevaluate:
            self._reevaluate_for_updated_research(user, workflow, context, reevaluate)

        return new_opportunities

    def _reevaluate_for_updated_research(
        self,
        user,
        workflow,
        context: dict,
        opportunities: list,
    ) -> None:
        from apps.agents.job_evaluation import JobEvaluationAgent

        agent = JobEvaluationAgent()
        for opportunity in opportunities:
            opportunity.job.refresh_from_db()
            agent._evaluate_opportunity(
                user, opportunity, workflow=workflow, context=context
            )

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
