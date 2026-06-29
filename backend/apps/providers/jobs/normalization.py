"""Normalize provider payloads into JobListing and dedupe keys."""

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

from apps.providers.jobs.base import JobListing


# Collapse common title variants before punctuation stripping (order matters).
_TITLE_TOKEN_SYNONYMS: tuple[tuple[str, str], ...] = (
    (r"\bfull\s*[-_]?\s*stack\b", "fullstack"),
    (r"\bfront\s*[-_]?\s*end\b", "frontend"),
    (r"\bback\s*[-_]?\s*end\b", "backend"),
)


def normalize_text(text: str) -> str:
    """Lowercase, collapse role synonyms, punctuation, and whitespace for dedupe."""
    if not text:
        return ""
    lowered = text.lower()
    for pattern, replacement in _TITLE_TOKEN_SYNONYMS:
        lowered = re.sub(pattern, replacement, lowered)
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_apply_url(url: str) -> str:
    """Canonical apply URL for dedupe (scheme, host, path — no query/fragment)."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    if not parsed.netloc:
        return url.strip().lower().rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


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
    company = _first_str(
        item, "company", "companyName", "company_name", "employer", "organization"
    )
    if not title or not company:
        return None

    location = _first_str(item, "location", "jobLocation", "city", "place")
    url = _first_str(item, "url", "link", "applyUrl", "jobUrl", "applicationUrl")
    description = _first_str(
        item, "description", "descriptionText", "snippet", "summary", "jobDescription"
    )
    external_id = _first_str(item, "id", "jobId", "externalId", "job_id", "listingId")
    if not external_id and url:
        canonical_url = normalize_apply_url(url) or url
        external_id = hashlib.sha256(canonical_url.encode()).hexdigest()[:32]

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
    """Stable dedupe key: normalized title+company+location, else URL, else source+external_id."""
    tcl_key = build_title_company_location_key(
        listing.title, listing.company, listing.location or ""
    )
    if tcl_key:
        return tcl_key

    normalized_url = normalize_apply_url(listing.url)
    if normalized_url:
        return hashlib.sha256(f"url:{normalized_url}".encode()).hexdigest()

    if listing.external_id and listing.source:
        raw = f"{listing.source}:{listing.external_id.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    return hashlib.sha256(b"unknown").hexdigest()


def build_title_company_location_key(title: str, company: str, location: str) -> str:
    """Lookup key for title + company + location fallback matching."""
    parts = [
        normalize_text(title),
        normalize_text(company),
        normalize_text(location or ""),
    ]
    normalized = "|".join(p for p in parts if p)
    if not normalized:
        return ""
    return hashlib.sha256(f"tcl:{normalized}".encode()).hexdigest()


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
