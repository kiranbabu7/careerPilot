"""Deduplication normalization and key generation tests."""

from apps.providers.jobs.base import JobListing
from apps.providers.jobs.normalization import (
    build_dedupe_key,
    build_title_company_location_key,
    normalize_apify_item,
    normalize_text,
)

RIPPLING_BASE = {
    "companyName": "Rippling",
    "location": "Bengaluru, Karnataka, India",
    "url": "https://www.linkedin.com/jobs/view/123",
    "description": "Build payroll and HR platform.",
    "source": "linkedin",
}


class TestNormalizeTextDedupe:
    def test_fullstack_title_variants_normalize_same(self):
        variants = [
            "Senior Software Engineer - Frontend/Fullstack",
            "Senior Software Engineer - Frontend Full Stack",
            "Senior Software Engineer - Frontend Full-Stack",
        ]
        keys = {normalize_text(title) for title in variants}
        assert len(keys) == 1
        assert keys.pop() == "senior software engineer frontend fullstack"

    def test_frontend_and_backend_titles_stay_distinct(self):
        frontend = normalize_text("Senior Software Engineer - Frontend/Fullstack")
        backend = normalize_text("Senior Software Engineer - Backend/Fullstack")
        assert frontend != backend

    def test_slash_and_space_punctuation_equivalent(self):
        a = normalize_text("Engineer - Platform/Infra")
        b = normalize_text("Engineer - Platform Infra")
        assert a == b


class TestBuildDedupeKey:
    def test_same_role_different_linkedin_ids_share_key(self):
        listings = [
            normalize_apify_item(
                {
                    **RIPPLING_BASE,
                    "id": "111",
                    "title": "Senior Software Engineer - Frontend/Fullstack",
                    "link": "https://www.linkedin.com/jobs/view/111",
                },
                source="linkedin",
            ),
            normalize_apify_item(
                {
                    **RIPPLING_BASE,
                    "id": "222",
                    "title": "Senior Software Engineer - Frontend Full Stack",
                    "link": "https://www.linkedin.com/jobs/view/222",
                },
                source="linkedin",
            ),
        ]
        assert listings[0] is not None and listings[1] is not None
        assert build_dedupe_key(listings[0]) == build_dedupe_key(listings[1])

    def test_different_role_tracks_remain_distinct(self):
        frontend = normalize_apify_item(
            {
                **RIPPLING_BASE,
                "id": "111",
                "title": "Senior Software Engineer - Frontend/Fullstack",
            },
            source="linkedin",
        )
        backend = normalize_apify_item(
            {
                **RIPPLING_BASE,
                "id": "333",
                "title": "Senior Software Engineer - Backend/Fullstack",
            },
            source="linkedin",
        )
        assert frontend is not None and backend is not None
        assert build_dedupe_key(frontend) != build_dedupe_key(backend)

    def test_title_company_location_key_matches_build_dedupe_key(self):
        listing = JobListing(
            external_id="ext-1",
            title="Staff Engineer",
            company="Acme",
            location="Remote",
            url="https://example.com/jobs/1",
            description="",
            source="linkedin",
        )
        assert build_dedupe_key(listing) == build_title_company_location_key(
            listing.title, listing.company, listing.location
        )

    def test_custom_prefixed_keys_not_used_for_listings(self):
        listing = JobListing(
            external_id="",
            title="Custom Role",
            company="Acme",
            location="NYC",
            url="",
            description="",
            source="custom",
        )
        key = build_dedupe_key(listing)
        assert not key.startswith("custom:")
