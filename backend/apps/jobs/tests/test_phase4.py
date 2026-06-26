"""Phase 4 tests — job discovery, providers, agents, APIs."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.job_search import JOB_SEARCH_AGENT_NAME, JobSearchAgent
from apps.agents.models import AgentExecution
from apps.jobs.models import Job, Opportunity
from apps.jobs.services import JobSearchService
from apps.providers.jobs.apify import (
    ApifyJobsProvider,
    build_actor_input,
    parse_actor_entry,
)
from apps.providers.jobs.base import JobListing
from apps.providers.jobs.normalization import build_dedupe_key, normalize_apify_item
from apps.providers.jobs.tavily_research import TavilyCompanyResearchProvider
from apps.resumes.tests.test_phase2 import user
from apps.workflows.models import WorkflowExecution
from apps.workflows.services import WorkflowService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def workflow(user):
    return WorkflowExecution.objects.create(
        user=user,
        name="Test workflow",
        goal="Find senior backend roles",
        status="completed",
    )


SAMPLE_APIFY_ITEM = {
    "id": "job-123",
    "title": "Senior Backend Engineer",
    "companyName": "Acme Corp",
    "location": "Remote",
    "url": "https://example.com/jobs/123",
    "description": "Python Django PostgreSQL",
    "isRemote": True,
    "salaryMin": 120000,
    "salaryMax": 160000,
}


class TestNormalization:
    def test_normalize_apify_item(self):
        listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        assert listing is not None
        assert listing.title == "Senior Backend Engineer"
        assert listing.company == "Acme Corp"
        assert listing.is_remote is True
        assert listing.salary_min == 120000

    def test_build_dedupe_key_from_external_id(self):
        listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        key1 = build_dedupe_key(listing)
        key2 = build_dedupe_key(listing)
        assert key1 == key2

    def test_dedupe_key_differs_for_different_jobs(self):
        a = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        b = normalize_apify_item(
            {**SAMPLE_APIFY_ITEM, "id": "job-456", "title": "Staff Engineer"},
            source="linkedin",
        )
        assert build_dedupe_key(a) != build_dedupe_key(b)


class TestApifyActorParsing:
    def test_bare_actor_id_defaults_to_linkedin(self):
        actor = parse_actor_entry("hKByXkMQaC5Qt9UMN")
        assert actor.actor_ref == "hKByXkMQaC5Qt9UMN"
        assert actor.source == "linkedin"

    def test_explicit_linkedin_prefix(self):
        actor = parse_actor_entry("linkedin:abc123")
        assert actor.actor_ref == "abc123"
        assert actor.source == "linkedin"

    def test_infers_source_from_actor_name(self):
        actor = parse_actor_entry("curious_coder/linkedin-jobs-scraper")
        assert actor.source == "linkedin"
        assert "linkedin" in actor.actor_ref

    def test_linkedin_actor_input_schema(self):
        payload = build_actor_input(
            source="linkedin",
            query="backend engineer",
            location="Remote",
            max_items=25,
        )
        assert payload == {
            "keywords": "backend engineer",
            "location": "Remote",
            "maxItems": 25,
            "searchQuery": "backend engineer",
        }


@pytest.mark.django_db
class TestApifyProvider:
    def test_parses_mocked_actor_response(self):
        mock_session = MagicMock()
        run_response = MagicMock()
        run_response.raise_for_status = MagicMock()
        run_response.json.return_value = {
            "data": {
                "status": "SUCCEEDED",
                "defaultDatasetId": "dataset-1",
            }
        }
        dataset_response = MagicMock()
        dataset_response.raise_for_status = MagicMock()
        dataset_response.json.return_value = [SAMPLE_APIFY_ITEM]
        mock_session.post.return_value = run_response
        mock_session.get.return_value = dataset_response

        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["linkedin/jobs-scraper"],
            session=mock_session,
        )
        listings = provider.search_jobs("backend engineer", location="Remote")
        assert len(listings) == 1
        assert listings[0].title == "Senior Backend Engineer"
        assert listings[0].source == "linkedin"

        posted_input = mock_session.post.call_args.kwargs["json"]
        assert posted_input["keywords"] == "backend engineer"
        assert posted_input["location"] == "Remote"
        assert posted_input["maxItems"] == 30

    def test_bare_actor_id_uses_linkedin_source(self):
        mock_session = MagicMock()
        run_response = MagicMock()
        run_response.raise_for_status = MagicMock()
        run_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-1"}
        }
        dataset_response = MagicMock()
        dataset_response.raise_for_status = MagicMock()
        dataset_response.json.return_value = [SAMPLE_APIFY_ITEM]
        mock_session.post.return_value = run_response
        mock_session.get.return_value = dataset_response

        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["hKByXkMQaC5Qt9UMN"],
            session=mock_session,
        )
        listings = provider.search_jobs("engineer")
        assert len(listings) == 1
        assert listings[0].source == "linkedin"

    def test_returns_empty_without_token(self):
        provider = ApifyJobsProvider(api_token="", actor_ids=["actor"])
        assert provider.search_jobs("query") == []


@pytest.mark.django_db
class TestTavilyResearch:
    def test_enrich_company_mocked(self):
        mock_session = MagicMock()
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "answer": "Acme is hiring aggressively.",
            "results": [
                {"title": "Acme News", "url": "https://news.example.com", "content": "Hiring spree"}
            ],
        }
        mock_session.post.return_value = response

        provider = TavilyCompanyResearchProvider(api_key="tvly-test", session=mock_session)
        result = provider.enrich_company("Acme Corp", job_title="Backend Engineer")
        assert result["available"] is True
        assert "hiring" in result["summary"].lower()
        assert len(result["snippets"]) == 1

    def test_skips_without_api_key(self):
        provider = TavilyCompanyResearchProvider(api_key="")
        result = provider.enrich_company("Acme")
        assert result["available"] is False


@pytest.mark.django_db
class TestJobSearchService:
    def test_deduplicates_and_persists(self, user, workflow):
        listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        duplicate = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")

        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing, duplicate]
        mock_apify.actor_ids = ["linkedin/jobs-scraper"]

        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {
            "Acme Corp": {"available": True, "summary": "Growing team", "snippets": []}
        }

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        context = {
            "goal": "Find backend roles",
            "preferences": {
                "target_roles": ["Backend Engineer"],
                "target_locations": ["Remote"],
                "skills": ["Python", "Django"],
            },
        }
        result = service.search(user, workflow, context)
        assert result["discovered_count"] == 1
        assert Job.objects.count() == 1
        assert Opportunity.objects.filter(user=user).count() == 1

        job = Job.objects.first()
        assert job.company_research.get("available") is True


@pytest.mark.django_db
class TestJobSearchAgent:
    def test_creates_agent_execution(self, user, workflow):
        mock_service = MagicMock()
        mock_service.search.return_value = {
            "query": "backend",
            "location": "",
            "discovered_count": 1,
            "total_listings": 1,
            "provider_summary": {"providers": {}, "errors": []},
            "errors": [],
            "opportunities": [],
        }

        agent = JobSearchAgent(search_service=mock_service)
        result = agent.search(
            user,
            workflow,
            {"goal": "backend", "preferences": {}},
        )
        assert result["discovered_count"] == 1
        execution = AgentExecution.objects.get(agent_name=JOB_SEARCH_AGENT_NAME)
        assert execution.status == "completed"
        assert execution.output_data["discovered_count"] == 1


@pytest.mark.django_db
class TestWorkflowIntegration:
    def test_start_workflow_runs_job_search(self, user):
        mock_listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="indeed")
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [mock_listing]
        mock_apify.actor_ids = ["indeed/scraper"]

        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = WorkflowService(
            job_search_agent=JobSearchAgent(
                search_service=JobSearchService(
                    apify_provider=mock_apify,
                    tavily_provider=mock_tavily,
                )
            ),
        )
        result = service.start_workflow(user, goal="Find backend engineer roles")
        assert result["discovered_count"] == 1
        assert "job_search_execution" in result
        assert result["workflow"]["result"]["discovered_count"] == 1
        assert Opportunity.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestOpportunitiesAPI:
    def test_list_requires_auth(self, api_client):
        response = api_client.get(reverse("opportunity-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_returns_user_opportunities(self, api_client, user, workflow):
        job = Job.objects.create(
            external_id="ext-1",
            source="linkedin",
            title="Engineer",
            company="Acme",
            dedupe_key="abc123",
        )
        Opportunity.objects.create(user=user, job=job, workflow_execution=workflow)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("opportunity-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["job"]["title"] == "Engineer"

    def test_detail_not_found(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("opportunity-detail", kwargs={"opportunity_id": "00000000-0000-0000-0000-000000000001"})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_workflow_job_search_rerun(self, api_client, user, workflow):
        api_client.force_authenticate(user=user)
        with patch.object(JobSearchService, "search") as mock_search:
            mock_search.return_value = {
                "query": "test",
                "location": "",
                "discovered_count": 0,
                "total_listings": 0,
                "provider_summary": {"providers": {}, "errors": []},
                "errors": [],
                "opportunities": [],
            }
            response = api_client.post(
                reverse("workflow-job-search", kwargs={"workflow_id": workflow.id})
            )
        assert response.status_code == status.HTTP_200_OK
        assert "job_search_execution" in response.data
