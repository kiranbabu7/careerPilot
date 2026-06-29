"""Apify actor-based job discovery provider."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from apify_client import ApifyClient
from django.conf import settings
from django.utils import timezone

from apps.providers.jobs.base import JobListing, JobProvider
from apps.providers.jobs.normalization import normalize_apify_item

logger = logging.getLogger(__name__)

KNOWN_SOURCES = ("linkedin", "naukri", "foundit", "indeed", "google")
SOURCE_PREFIX_RE = re.compile(
    rf"^({'|'.join(KNOWN_SOURCES)})\s*[:/]\s*(.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ApifyActorConfig:
    """Resolved actor reference plus job-board source label."""

    actor_ref: str
    source: str


def parse_actor_entry(entry: str, *, default_source: str = "linkedin") -> ApifyActorConfig:
    """Parse APIFY_JOB_ACTOR_IDS entries into actor ref and source.

    Supported formats:
    - ``linkedin:hKByXkMQaC5Qt9UMN`` — explicit source + Apify actor ID
    - ``curious_coder/linkedin-jobs-scraper`` — username/actor-name (source inferred)
    - ``hKByXkMQaC5Qt9UMN`` — bare actor ID (defaults to ``default_source``)
    """
    raw = entry.strip()
    if not raw:
        raise ValueError("Empty Apify actor entry")

    match = SOURCE_PREFIX_RE.match(raw)
    if match:
        return ApifyActorConfig(
            actor_ref=match.group(2).strip(),
            source=match.group(1).lower(),
        )

    lowered = raw.lower()
    for name in KNOWN_SOURCES:
        if name in lowered:
            return ApifyActorConfig(actor_ref=raw, source=name)

    return ApifyActorConfig(actor_ref=raw, source=default_source)


LINKEDIN_JOBS_SEARCH_BASE = "https://www.linkedin.com/jobs/search/"
MAX_LINKEDIN_SEARCH_URLS = 3
MAX_SKILLS_PER_ROLE = 2
DEFAULT_SPLIT_COUNTRY = "IN"

# Location substrings mapped to Apify splitCountry ISO codes (curious_coder actor).
LOCATION_COUNTRY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "india",
            "hyderabad",
            "bangalore",
            "bengaluru",
            "telangana",
            "mumbai",
            "delhi",
            "pune",
            "chennai",
            "kolkata",
            "gurgaon",
            "gurugram",
            "noida",
        ),
        "IN",
    ),
    (
        (
            "united states",
            "usa",
            "u.s.",
            "new york",
            "san francisco",
            "california",
            "texas",
            "seattle",
            "boston",
            "chicago",
            "washington, dc",
        ),
        "US",
    ),
    (("canada", "toronto", "vancouver", "montreal", "ottawa"), "CA"),
    (("united kingdom", "uk", "london", "england", "scotland"), "GB"),
    (("australia", "sydney", "melbourne"), "AU"),
    (("germany", "berlin", "munich"), "DE"),
    (("singapore",), "SG"),
)

SPLIT_COUNTRY_LINKEDIN_LOCATIONS: dict[str, str] = {
    "IN": "India",
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "AU": "Australia",
    "DE": "Germany",
    "SG": "Singapore",
}

REMOTE_LOCATION_TERMS = frozenset({"remote", "work from home", "wfh", "anywhere"})

SENIOR_ROLE_KEYWORDS = (
    "staff",
    "principal",
    "lead",
    "architect",
    "director",
    "head",
    "vp ",
    "vice president",
)
MID_SENIOR_ROLE_KEYWORDS = ("senior", "sr.", "sr ")
JUNIOR_ROLE_KEYWORDS = (
    "junior",
    "jr.",
    "jr ",
    "entry",
    "intern",
    "graduate",
    "fresher",
)


def resolve_split_country(
    target_locations: list[str] | None,
    remote_preference: str = "flexible",
) -> str:
    """Map user target locations to a valid Apify splitCountry ISO code."""
    del remote_preference  # reserved for future remote-only heuristics
    locations = [loc.strip() for loc in (target_locations or []) if loc and loc.strip()]

    for loc in locations:
        lowered = loc.lower()
        if lowered in REMOTE_LOCATION_TERMS:
            continue
        for hints, code in LOCATION_COUNTRY_HINTS:
            if any(hint in lowered for hint in hints):
                return code
        if len(loc) == 2 and loc.isalpha():
            return loc.upper()

    return DEFAULT_SPLIT_COUNTRY


def linkedin_location_for_country(country_code: str) -> str:
    """LinkedIn jobs search location label for a splitCountry ISO code."""
    return SPLIT_COUNTRY_LINKEDIN_LOCATIONS.get(
        country_code.upper(),
        SPLIT_COUNTRY_LINKEDIN_LOCATIONS[DEFAULT_SPLIT_COUNTRY],
    )


def resolve_linkedin_location(
    target_locations: list[str] | None,
    remote_preference: str = "flexible",
) -> str:
    """Pick LinkedIn location param from preferences, defaulting by country."""
    locations = [loc.strip() for loc in (target_locations or []) if loc and loc.strip()]
    non_remote = [loc for loc in locations if loc.lower() not in REMOTE_LOCATION_TERMS]
    if non_remote:
        return non_remote[0]

    country = resolve_split_country(locations, remote_preference)
    return linkedin_location_for_country(country)


def linkedin_work_type_filter(remote_preference: str) -> str:
    """Map remote preference to LinkedIn f_WT filter values."""
    pref = (remote_preference or "flexible").lower()
    mapping = {
        "remote": "2",
        "hybrid": "1,2",
        "onsite": "1",
        "on-site": "1",
        "on_site": "1",
        "flexible": "1,2",
    }
    return mapping.get(pref, "1,2")


def linkedin_experience_filter(roles: list[str]) -> str:
    """Infer LinkedIn f_E experience filter from target roles."""
    text = " ".join(roles).lower()
    if any(keyword in text for keyword in SENIOR_ROLE_KEYWORDS):
        return "4,5"
    if any(keyword in text for keyword in JUNIOR_ROLE_KEYWORDS):
        return "2,3"
    if any(keyword in text for keyword in MID_SENIOR_ROLE_KEYWORDS):
        return "3,4"
    return "3,4"


def build_linkedin_role_keywords(role: str, skills: list[str]) -> str:
    """Combine a target role with up to two resume skills for search keywords."""
    role_text = role.strip()
    skill_terms = [s.strip() for s in skills if s and s.strip()][:MAX_SKILLS_PER_ROLE]
    if not role_text:
        return " ".join(skill_terms) if skill_terms else "software engineer"
    if not skill_terms:
        return role_text
    return f"{role_text} {' '.join(skill_terms)}"


def linkedin_time_posted_filter(posted_since: datetime | None) -> str | None:
    """Map a posted-since cutoff to LinkedIn f_TPR time-posted buckets."""
    if posted_since is None:
        return None

    now = timezone.now()
    if timezone.is_naive(posted_since):
        posted_since = timezone.make_aware(posted_since, timezone.get_current_timezone())

    elapsed = now - posted_since
    if elapsed <= timedelta(hours=1):
        return "r3600"
    if elapsed <= timedelta(hours=24):
        return "r86400"
    return "r604800"


def build_linkedin_job_search_url(
    *,
    keywords: str,
    location: str,
    work_type_filter: str,
    experience_filter: str,
    posted_since: datetime | None = None,
) -> str:
    """Build a LinkedIn jobs search URL matching the curious_coder actor input format."""
    params = {
        "keywords": keywords,
        "location": location,
        "f_WT": work_type_filter,
        "f_E": experience_filter,
    }
    time_posted = linkedin_time_posted_filter(posted_since)
    if time_posted:
        params["f_TPR"] = time_posted
    return f"{LINKEDIN_JOBS_SEARCH_BASE}?{urlencode(params)}"


def build_linkedin_search_urls(
    *,
    roles: list[str],
    skills: list[str],
    location: str,
    remote_preference: str,
    max_urls: int = MAX_LINKEDIN_SEARCH_URLS,
    posted_since: datetime | None = None,
) -> list[str]:
    """Build 1-3 LinkedIn job search URLs, one per top target role."""
    cleaned_roles = [role.strip() for role in roles if role and role.strip()]
    if not cleaned_roles:
        cleaned_roles = ["software engineer"]

    work_type = linkedin_work_type_filter(remote_preference)
    location_text = location.strip() or linkedin_location_for_country(DEFAULT_SPLIT_COUNTRY)

    urls: list[str] = []
    for role in cleaned_roles[:max_urls]:
        keywords = build_linkedin_role_keywords(role, skills)
        experience = linkedin_experience_filter([role])
        urls.append(
            build_linkedin_job_search_url(
                keywords=keywords,
                location=location_text,
                work_type_filter=work_type,
                experience_filter=experience,
                posted_since=posted_since,
            )
        )
    return urls


def build_actor_input(
    *,
    source: str,
    query: str,
    location: str,
    max_items: int,
    urls: list[str] | None = None,
    split_country: str | None = None,
) -> dict[str, Any]:
    """Build actor input for Apify job board actors."""
    limit = max(1, max_items)

    if source == "linkedin":
        linkedin_urls = [url.strip() for url in (urls or []) if url and url.strip()]
        country = (split_country or DEFAULT_SPLIT_COUNTRY).strip().upper()
        if not country:
            country = DEFAULT_SPLIT_COUNTRY
        return {
            "urls": linkedin_urls,
            "count": limit,
            "scrapeCompany": True,
            "splitByLocation": False,
            "splitCountry": country,
        }

    return {
        "query": query,
        "location": location,
        "maxItems": limit,
    }


def normalize_actor_id(actor_ref: str) -> str:
    """Normalize actor refs for ApifyClient (``user/name`` -> ``user~name``)."""
    if "/" in actor_ref and "~" not in actor_ref:
        return actor_ref.replace("/", "~", 1)
    return actor_ref


class ApifyJobsProvider(JobProvider):
    """Runs configured Apify actors for job board scraping."""

    def __init__(
        self,
        *,
        api_token: str | None = None,
        actor_ids: list[str] | None = None,
        dataset_limit: int | None = None,
        max_results: int | None = None,
        client: ApifyClient | None = None,
    ):
        self.api_token = api_token if api_token is not None else settings.APIFY_API_TOKEN
        self.actor_ids = actor_ids if actor_ids is not None else settings.APIFY_JOB_ACTOR_IDS
        self.dataset_limit = (
            dataset_limit
            if dataset_limit is not None
            else settings.APIFY_DEFAULT_DATASET_LIMIT
        )
        self.max_results = (
            max_results if max_results is not None else settings.JOB_SEARCH_MAX_RESULTS
        )
        self._client = client
        self.last_search_errors: list[str] = []

    @property
    def provider_name(self) -> str:
        return "apify"

    def _get_client(self) -> ApifyClient:
        if self._client is not None:
            return self._client
        return ApifyClient(self.api_token)

    def _resolve_max_items(self, requested: int | None) -> int:
        """Cap requested item count; None means use provider default."""
        limit = self.max_results if requested is None else requested
        return min(limit, self.max_results)

    def search_jobs(self, query: str, **kwargs) -> list[JobListing]:
        if not self.api_token:
            logger.warning("Apify API token not configured; skipping job discovery")
            return []

        if not self.actor_ids:
            logger.warning("No Apify job actor IDs configured; skipping job discovery")
            return []

        location = kwargs.get("location", "")
        urls = kwargs.get("urls")
        split_country = kwargs.get("split_country", DEFAULT_SPLIT_COUNTRY)
        max_items = self._resolve_max_items(kwargs.get("max_items"))
        logger.info(
            "Apify job search starting query=%r location=%r urls=%s actors=%s max_items=%s",
            query,
            location,
            urls,
            self.actor_ids,
            max_items,
        )
        all_listings: list[JobListing] = []
        seen_keys: set[str] = set()
        self.last_search_errors = []

        for actor_entry in self.actor_ids:
            if len(all_listings) >= max_items:
                break
            try:
                actor = parse_actor_entry(actor_entry)
                if actor.source == "linkedin" and not urls:
                    logger.warning(
                        "Skipping LinkedIn actor %s: no search urls provided",
                        actor.actor_ref,
                    )
                    continue

                actor_urls = urls if actor.source == "linkedin" else None
                items = self._run_actor(
                    actor,
                    query,
                    location,
                    max_items,
                    urls=actor_urls,
                    split_country=split_country,
                )
                logger.info(
                    "Apify actor %s (%s) returned %s raw items",
                    actor.actor_ref,
                    actor.source,
                    len(items),
                )
                for item in items:
                    listing = normalize_apify_item(item, source=actor.source)
                    if listing is None:
                        continue
                    key = f"{listing.source}:{listing.external_id or listing.url}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    all_listings.append(listing)
                    if len(all_listings) >= max_items:
                        break
            except Exception as exc:
                logger.exception("Apify actor %s failed: %s", actor_entry, exc)
                self.last_search_errors.append(f"{actor_entry}: {exc}")
                continue

        logger.info(
            "Apify job search finished query=%r normalized_listings=%s",
            query,
            len(all_listings),
        )
        return all_listings[:max_items]

    def get_job(self, external_id: str) -> JobListing | None:
        return None

    def _run_actor(
        self,
        actor: ApifyActorConfig,
        query: str,
        location: str,
        max_items: int,
        *,
        urls: list[str] | None = None,
        split_country: str = DEFAULT_SPLIT_COUNTRY,
    ) -> list[dict[str, Any]]:
        actor_id = normalize_actor_id(actor.actor_ref)
        actor_input = build_actor_input(
            source=actor.source,
            query=query,
            location=location,
            max_items=min(max_items, self.dataset_limit),
            urls=urls,
            split_country=split_country,
        )
        logger.info(
            "Apify run starting actor_id=%s source=%s run_input=%s",
            actor.actor_ref,
            actor.source,
            actor_input,
        )

        client = self._get_client()
        run = client.actor(actor_id).call(run_input=actor_input)
        status = run.get("status")
        run_id = run.get("id")
        logger.info(
            "Apify run finished actor_id=%s run_id=%s status=%s",
            actor.actor_ref,
            run_id,
            status,
        )

        if status != "SUCCEEDED":
            logger.warning(
                "Apify actor %s finished with status %s run_id=%s",
                actor.actor_ref,
                status,
                run_id,
            )
            logger.debug("Apify failed run payload=%s", run)
            return []

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            logger.warning(
                "Apify actor %s succeeded but no dataset id run_id=%s",
                actor.actor_ref,
                run_id,
            )
            return []

        items = self._fetch_dataset(client, dataset_id)
        logger.info(
            "Apify dataset fetched actor_id=%s dataset_id=%s item_count=%s",
            actor.actor_ref,
            dataset_id,
            len(items),
        )
        if items:
            sample = items[0]
            logger.info(
                "Apify sample result actor_id=%s title=%r company=%r",
                actor.actor_ref,
                sample.get("title") or sample.get("jobTitle"),
                sample.get("companyName")
                or sample.get("company")
                or sample.get("company_name"),
            )
            logger.debug("Apify first raw item actor_id=%s item=%s", actor.actor_ref, sample)
        else:
            logger.info(
                "Apify dataset empty actor_id=%s query=%r location=%r urls=%s",
                actor.actor_ref,
                query,
                location,
                urls,
            )
        return items

    def _fetch_dataset(self, client: ApifyClient, dataset_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item in client.dataset(dataset_id).iterate_items(limit=self.dataset_limit):
            if isinstance(item, dict):
                items.append(item)
        return items
