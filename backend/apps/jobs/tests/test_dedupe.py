"""Job search deduplication and duplicate opportunity skip tests."""

from unittest.mock import MagicMock

import pytest

from apps.jobs.models import Job, Opportunity
from apps.jobs.services import JobSearchService
from apps.providers.jobs.normalization import normalize_apify_item
from apps.resumes.tests.test_phase2 import user
from apps.workflows.models import WorkflowExecution

RIPPLING_ITEM_A = {
    "id": "rippling-frontend-1",
    "title": "Senior Software Engineer - Frontend/Fullstack",
    "companyName": "Rippling",
    "location": "Bengaluru, Karnataka, India",
    "link": "https://www.linkedin.com/jobs/view/rippling-frontend-1",
    "descriptionText": "React TypeScript Node payroll platform.",
}

RIPPLING_ITEM_B = {
    "id": "rippling-frontend-2",
    "title": "Senior Software Engineer - Frontend Full Stack",
    "companyName": "Rippling",
    "location": "Bengaluru, Karnataka, India",
    "link": "https://www.linkedin.com/jobs/view/rippling-frontend-2",
    "descriptionText": "React TypeScript Node payroll platform.",
}

RIPPLING_ITEM_BACKEND = {
    "id": "rippling-backend-1",
    "title": "Senior Software Engineer - Backend/Fullstack",
    "companyName": "Rippling",
    "location": "Bengaluru, Karnataka, India",
    "link": "https://www.linkedin.com/jobs/view/rippling-backend-1",
    "descriptionText": "Python Go distributed systems payroll platform.",
}


@pytest.fixture
def workflow(user):
    return WorkflowExecution.objects.create(
        user=user,
        name="Dedupe workflow",
        goal="Find senior roles",
        status="completed",
    )


def _search_service_with_listings(listings):
    mock_apify = MagicMock()
    mock_apify.search_jobs.return_value = listings
    mock_apify.actor_ids = ["linkedin/jobs-scraper"]
    mock_apify.api_token = "test-token"
    mock_tavily = MagicMock()
    mock_tavily.enrich_jobs.return_value = {}
    return JobSearchService(apify_provider=mock_apify, tavily_provider=mock_tavily)


@pytest.mark.django_db
class TestJobSearchDedupe:
    def test_title_variants_in_one_search_create_single_job_and_opportunity(
        self, user, workflow
    ):
        listings = [
            normalize_apify_item(RIPPLING_ITEM_A, source="linkedin"),
            normalize_apify_item(RIPPLING_ITEM_B, source="linkedin"),
        ]
        service = _search_service_with_listings(listings)
        context = {
            "goal": "Find senior frontend roles",
            "preferences": {"target_roles": ["Senior Software Engineer"]},
        }

        result = service.search(user, workflow, context)

        assert result["discovered_count"] == 1
        assert Job.objects.count() == 1
        assert Opportunity.objects.filter(user=user).count() == 1

    def test_frontend_and_backend_tracks_both_kept(self, user, workflow):
        listings = [
            normalize_apify_item(RIPPLING_ITEM_A, source="linkedin"),
            normalize_apify_item(RIPPLING_ITEM_BACKEND, source="linkedin"),
        ]
        service = _search_service_with_listings(listings)
        context = {
            "goal": "Find senior roles",
            "preferences": {"target_roles": ["Senior Software Engineer"]},
        }

        result = service.search(user, workflow, context)

        assert result["discovered_count"] == 2
        assert Job.objects.count() == 2
        assert Opportunity.objects.filter(user=user).count() == 2

    def test_repeat_search_skips_equivalent_opportunity(self, user, workflow):
        listing_a = normalize_apify_item(RIPPLING_ITEM_A, source="linkedin")
        service = _search_service_with_listings([listing_a])
        context = {
            "goal": "Find senior frontend roles",
            "preferences": {"target_roles": ["Senior Software Engineer"]},
        }
        first = service.search(user, workflow, context)
        assert first["discovered_count"] == 1

        listing_b = normalize_apify_item(RIPPLING_ITEM_B, source="linkedin")
        service_b = _search_service_with_listings([listing_b])
        second = service_b.search(user, workflow, context)

        assert second["discovered_count"] == 0
        assert Job.objects.count() == 1
        assert Opportunity.objects.filter(user=user).count() == 1

    def test_legacy_job_with_external_id_dedupe_still_merges(self, user, workflow):
        """Pre-fix jobs keyed by external_id should merge on title+company+location."""
        from apps.jobs.models import OpportunityStatus

        legacy_job = Job.objects.create(
            external_id="rippling-frontend-1",
            source="linkedin",
            title="Senior Software Engineer - Frontend/Fullstack",
            company="Rippling",
            location="Bengaluru, Karnataka, India",
            description="React TypeScript",
            dedupe_key="legacy-external-id-key",
        )
        Opportunity.objects.create(
            user=user,
            job=legacy_job,
            workflow_execution=workflow,
            status=OpportunityStatus.DISCOVERED,
            source_agent="job_search",
        )
        listing = normalize_apify_item(RIPPLING_ITEM_B, source="linkedin")
        service = _search_service_with_listings([listing])
        context = {
            "goal": "Find senior frontend roles",
            "preferences": {"target_roles": ["Senior Software Engineer"]},
        }

        result = service.search(user, workflow, context)

        assert result["discovered_count"] == 0
        assert Job.objects.count() == 1
        assert Opportunity.objects.filter(user=user).count() == 1
