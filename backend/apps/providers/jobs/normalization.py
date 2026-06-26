"""Normalize provider payloads into JobListing and dedupe keys."""

import hashlib
import re
from datetime import datetime
from typing import Any

from apps.providers.jobs.base import JobListing


def _first_str(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            nested = value.get("name") or value.get("title") or value.get("label")
            if nested:
                return str(nested).strip()
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("true", "1", "yes", "remote", "hybrid")


def _parse_salary(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d.]", "", str(value))
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_apify_item(item: dict[str, Any], *, source: str) -> JobListing | None:
    title = _first_str(item, "title", "jobTitle", "position", "role", "name")
    company = _first_str(item, "company", "companyName", "employer", "organization")
    if not title or not company:
        return None

    location = _first_str(item, "location", "jobLocation", "city", "place")
    url = _first_str(item, "url", "link", "applyUrl", "jobUrl", "applicationUrl")
    description = _first_str(item, "description", "snippet", "summary", "jobDescription")
    external_id = _first_str(item, "id", "jobId", "externalId", "job_id", "listingId")
    if not external_id and url:
        external_id = hashlib.sha256(url.encode()).hexdigest()[:32]

    salary_min = _parse_salary(
        item.get("salaryMin") or item.get("salary_min") or item.get("minSalary")
    )
    salary_max = _parse_salary(
        item.get("salaryMax") or item.get("salary_max") or item.get("maxSalary")
    )
    if salary_min is None and salary_max is None:
        salary_text = _first_str(item, "salary", "compensation", "pay")
        if salary_text:
            numbers = re.findall(r"[\d,]+", salary_text.replace(",", ""))
            if numbers:
                parsed = [_parse_salary(n) for n in numbers[:2]]
                parsed = [p for p in parsed if p is not None]
                if parsed:
                    salary_min = parsed[0]
                    salary_max = parsed[-1] if len(parsed) > 1 else parsed[0]

    is_remote = _parse_bool(
        item.get("isRemote")
        or item.get("remote")
        or item.get("workFromHome")
        or ("remote" in location.lower() if location else False)
    )

    posted_at = _first_str(item, "postedAt", "posted_at", "datePosted", "publishedAt")
    salary_currency = _first_str(item, "salaryCurrency", "currency") or "USD"

    return JobListing(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=url,
        description=description,
        source=source,
        is_remote=is_remote,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        posted_at=posted_at or None,
        raw_payload=item,
    )


def build_dedupe_key(listing: JobListing) -> str:
    if listing.external_id and listing.source:
        return hashlib.sha256(
            f"{listing.source}:{listing.external_id}".lower().encode()
        ).hexdigest()

    parts = [
        listing.title.lower().strip(),
        listing.company.lower().strip(),
        listing.location.lower().strip(),
        listing.url.lower().strip(),
    ]
    normalized = "|".join(p for p in parts if p)
    return hashlib.sha256(normalized.encode()).hexdigest()


def parse_posted_at(value: str | None):
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            from django.utils import timezone

            dt = datetime.strptime(value[:26], fmt)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        except ValueError:
            continue
    return None
