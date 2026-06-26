"""Apify actor-based job discovery provider."""

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

from apps.providers.jobs.base import JobListing, JobProvider
from apps.providers.jobs.normalization import normalize_apify_item

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"
DEFAULT_WAIT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2
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


def build_actor_input(
    *,
    source: str,
    query: str,
    location: str,
    max_items: int,
) -> dict[str, Any]:
    """Build actor input using the schema common to each job board."""
    limit = max(1, max_items)

    if source == "linkedin":
        payload: dict[str, Any] = {
            "keywords": query,
            "location": location,
            "maxItems": limit,
        }
        if query:
            payload["searchQuery"] = query
        return payload

    payload = {
        "query": query,
        "keywords": query,
        "search": query,
        "location": location,
        "maxItems": limit,
        "limit": limit,
        "count": limit,
    }
    if source == "indeed":
        payload["query"] = query
    return payload


class ApifyJobsProvider(JobProvider):
    """Runs configured Apify actors for job board scraping."""

    def __init__(
        self,
        *,
        api_token: str | None = None,
        actor_ids: list[str] | None = None,
        dataset_limit: int | None = None,
        max_results: int | None = None,
        session: requests.Session | None = None,
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
        self.session = session or requests.Session()

    @property
    def provider_name(self) -> str:
        return "apify"

    def search_jobs(self, query: str, **kwargs) -> list[JobListing]:
        if not self.api_token:
            logger.warning("Apify API token not configured; skipping job discovery")
            return []

        if not self.actor_ids:
            logger.warning("No Apify job actor IDs configured; skipping job discovery")
            return []

        location = kwargs.get("location", "")
        max_items = min(
            kwargs.get("max_items", self.max_results),
            self.max_results,
        )
        all_listings: list[JobListing] = []
        seen_keys: set[str] = set()

        for actor_entry in self.actor_ids:
            if len(all_listings) >= max_items:
                break
            try:
                actor = parse_actor_entry(actor_entry)
                items = self._run_actor(actor, query, location, max_items)
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
                continue

        return all_listings[:max_items]

    def get_job(self, external_id: str) -> JobListing | None:
        return None

    def _run_actor(
        self, actor: ApifyActorConfig, query: str, location: str, max_items: int
    ) -> list[dict[str, Any]]:
        actor_ref = actor.actor_ref.replace("/", "~")
        run_url = (
            f"{APIFY_BASE_URL}/acts/{actor_ref}/runs"
            f"?token={self.api_token}&waitForFinish={DEFAULT_WAIT_SECONDS}"
        )
        actor_input = build_actor_input(
            source=actor.source,
            query=query,
            location=location,
            max_items=min(max_items, self.dataset_limit),
        )

        response = self.session.post(
            run_url,
            json=actor_input,
            timeout=DEFAULT_WAIT_SECONDS + 30,
        )
        response.raise_for_status()
        run_data = response.json().get("data", {})
        status = run_data.get("status")
        run_id = run_data.get("id")

        if status not in ("SUCCEEDED", "READY", "RUNNING") and run_id:
            run_data = self._wait_for_run(actor_ref, run_id)
            status = run_data.get("status")

        if status != "SUCCEEDED":
            logger.warning(
                "Apify actor %s finished with status %s", actor.actor_ref, status
            )
            if status == "FAILED":
                return []

        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            return []

        return self._fetch_dataset(dataset_id)

    def _wait_for_run(self, actor_ref: str, run_id: str) -> dict[str, Any]:
        deadline = time.time() + DEFAULT_WAIT_SECONDS
        while time.time() < deadline:
            response = self.session.get(
                f"{APIFY_BASE_URL}/actor-runs/{run_id}?token={self.api_token}",
                timeout=30,
            )
            response.raise_for_status()
            run_data = response.json().get("data", {})
            if run_data.get("status") in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                return run_data
            time.sleep(POLL_INTERVAL_SECONDS)
        return run_data

    def _fetch_dataset(self, dataset_id: str) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
            params={
                "token": self.api_token,
                "limit": self.dataset_limit,
                "format": "json",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        return []
