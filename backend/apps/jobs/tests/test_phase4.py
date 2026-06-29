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
    build_linkedin_job_search_url,
    build_linkedin_search_urls,
    linkedin_experience_filter,
    linkedin_work_type_filter,
    parse_actor_entry,
    resolve_split_country,
)
from apps.providers.jobs.base import JobListing
from apps.providers.jobs.normalization import (
    build_dedupe_key,
    normalize_apify_item,
    normalize_apply_url,
)
from apps.providers.jobs.company_research_synthesis import build_research_queries
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

SAMPLE_LINKEDIN_APIFY_ITEM = {
    "id": "3692563200",
    "link": "https://www.linkedin.com/jobs/view/senior-backend-engineer-3692563200",
    "title": "Senior Backend Engineer",
    "companyName": "Acme Corp",
    "location": "Hyderabad, Telangana, India",
    "descriptionText": "Python Django PostgreSQL AWS",
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

    def test_dedupe_key_same_for_url_with_different_query(self):
        a = normalize_apify_item(
            {**SAMPLE_APIFY_ITEM, "id": "", "url": "https://example.com/jobs/123?ref=1"},
            source="linkedin",
        )
        b = normalize_apify_item(
            {**SAMPLE_APIFY_ITEM, "id": "", "url": "https://example.com/jobs/123?ref=2"},
            source="linkedin",
        )
        assert build_dedupe_key(a) == build_dedupe_key(b)

    def test_normalize_apply_url_strips_query(self):
        url = "https://LinkedIn.com/jobs/view/123/?tracking=abc"
        assert normalize_apply_url(url) == "https://linkedin.com/jobs/view/123"

    def test_normalize_linkedin_actor_item(self):
        listing = normalize_apify_item(SAMPLE_LINKEDIN_APIFY_ITEM, source="linkedin")
        assert listing is not None
        assert listing.title == "Senior Backend Engineer"
        assert listing.company == "Acme Corp"
        assert "linkedin.com" in listing.url
        assert "Python Django" in listing.description


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

    def test_linkedin_actor_input_schema_with_urls(self):
        urls = [
            "https://www.linkedin.com/jobs/search/?keywords=backend&location=India&f_WT=2&f_E=3%2C4"
        ]
        payload = build_actor_input(
            source="linkedin",
            query="backend engineer",
            location="Remote",
            max_items=50,
            urls=urls,
            split_country="IN",
        )
        assert payload == {
            "urls": urls,
            "count": 50,
            "scrapeCompany": True,
            "splitByLocation": False,
            "splitCountry": "IN",
        }

    def test_linkedin_actor_input_defaults_split_country_to_in(self):
        payload = build_actor_input(
            source="linkedin",
            query="backend engineer",
            location="Remote",
            max_items=10,
            urls=["https://www.linkedin.com/jobs/search/?keywords=backend"],
        )
        assert payload["splitCountry"] == "IN"
        assert isinstance(payload["splitCountry"], str)
        assert payload["splitCountry"] != ""

    def test_non_linkedin_actor_input_schema(self):
        payload = build_actor_input(
            source="indeed",
            query="backend engineer",
            location="Remote",
            max_items=25,
        )
        assert payload == {
            "query": "backend engineer",
            "location": "Remote",
            "maxItems": 25,
        }


class TestResolveSplitCountry:
    def test_hyderabad_maps_to_in(self):
        assert resolve_split_country(["Hyderabad, Telangana, India"]) == "IN"

    def test_bangalore_maps_to_in(self):
        assert resolve_split_country(["Bangalore"]) == "IN"

    def test_us_location_maps_to_us(self):
        assert resolve_split_country(["San Francisco, California, USA"]) == "US"

    def test_defaults_to_in_without_locations(self):
        assert resolve_split_country([], remote_preference="remote") == "IN"

    def test_remote_only_location_defaults_to_in(self):
        assert resolve_split_country(["Remote"], remote_preference="remote") == "IN"


class TestLinkedInUrlBuilding:
    def test_work_type_filter_mapping(self):
        assert linkedin_work_type_filter("remote") == "2"
        assert linkedin_work_type_filter("hybrid") == "1,2"
        assert linkedin_work_type_filter("onsite") == "1"
        assert linkedin_work_type_filter("flexible") == "1,2"

    def test_experience_filter_infers_staff_roles(self):
        assert linkedin_experience_filter(["Staff Software Engineer"]) == "4,5"

    def test_experience_filter_treats_senior_as_mid_senior(self):
        assert linkedin_experience_filter(["Senior Software Engineer"]) == "3,4"

    def test_experience_filter_defaults_to_mid_senior(self):
        assert linkedin_experience_filter(["Software Engineer"]) == "3,4"

    def test_build_linkedin_job_search_url(self):
        url = build_linkedin_job_search_url(
            keywords="Senior Software Engineer Python Django",
            location="Hyderabad, Telangana, India",
            work_type_filter="1,2",
            experience_filter="3,4",
        )
        assert url.startswith("https://www.linkedin.com/jobs/search/?")
        assert "keywords=Senior+Software+Engineer+Python+Django" in url
        assert "location=Hyderabad%2C+Telangana%2C+India" in url
        assert "f_WT=1%2C2" in url
        assert "f_E=3%2C4" in url

    def test_build_linkedin_search_urls_one_per_role(self):
        urls = build_linkedin_search_urls(
            roles=["Senior Software Engineer", "SDE2"],
            skills=["Python", "Django", "AWS"],
            location="Hyderabad, Telangana, India",
            remote_preference="hybrid",
        )
        assert len(urls) == 2
        assert "Senior+Software+Engineer+Python+Django" in urls[0]
        assert "SDE2+Python+Django" in urls[1]
        assert all("f_WT=1%2C2" in url for url in urls)

    def test_service_builds_linkedin_urls_from_preferences(self):
        service = JobSearchService()
        context = {
            "goal": "Find backend roles",
            "preferences": {
                "target_roles": ["Senior Software Engineer", "SDE2"],
                "target_locations": ["Hyderabad, Telangana, India"],
                "skills": ["Python", "Django", "AWS"],
                "remote_preference": "hybrid",
            },
        }
        urls = service.build_linkedin_search_urls(context)
        assert len(urls) == 2
        assert "Hyderabad%2C+Telangana%2C+India" in urls[0]
        assert "Senior+Software+Engineer+Python+Django" in urls[0]
        assert "SDE2+Python+Django" in urls[1]

    def test_service_remote_preference_uses_india_when_no_location(self):
        service = JobSearchService()
        context = {
            "preferences": {
                "target_roles": ["SDE2"],
                "skills": ["Python", "Django", "AWS"],
                "remote_preference": "remote",
            }
        }
        urls = service.build_linkedin_search_urls(context)
        assert len(urls) == 1
        assert "location=India" in urls[0]
        assert "f_WT=2" in urls[0]


@pytest.mark.django_db
class TestApifyProvider:
    def _mock_apify_client(self, items):
        mock_client = MagicMock()
        mock_actor = MagicMock()
        mock_dataset = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {
            "status": "SUCCEEDED",
            "defaultDatasetId": "dataset-1",
            "id": "run-1",
        }
        mock_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = iter(items)
        return mock_client, mock_actor

    def test_parses_mocked_actor_response_with_linkedin_urls(self):
        mock_client, mock_actor = self._mock_apify_client([SAMPLE_LINKEDIN_APIFY_ITEM])

        linkedin_urls = [
            "https://www.linkedin.com/jobs/search/?keywords=backend&location=India&f_WT=2&f_E=3%2C4"
        ]
        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["hKByXkMQaC5Qt9UMN"],
            client=mock_client,
        )
        listings = provider.search_jobs(
            "backend engineer",
            location="Remote",
            urls=linkedin_urls,
            split_country="IN",
        )
        assert len(listings) == 1
        assert listings[0].title == "Senior Backend Engineer"
        assert listings[0].source == "linkedin"

        mock_client.actor.assert_called_once_with("hKByXkMQaC5Qt9UMN")
        run_input = mock_actor.call.call_args.kwargs["run_input"]
        assert run_input["urls"] == linkedin_urls
        assert run_input["count"] == 50
        assert run_input["scrapeCompany"] is True
        assert run_input["splitByLocation"] is False
        assert run_input["splitCountry"] == "IN"
        assert isinstance(run_input["splitCountry"], str)
        assert run_input["splitCountry"] != ""

    def test_bare_actor_id_uses_linkedin_source(self):
        mock_client, _mock_actor = self._mock_apify_client([SAMPLE_APIFY_ITEM])
        linkedin_urls = [
            "https://www.linkedin.com/jobs/search/?keywords=engineer&location=India&f_WT=1%2C2&f_E=3%2C4"
        ]

        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["hKByXkMQaC5Qt9UMN"],
            client=mock_client,
        )
        listings = provider.search_jobs("engineer", urls=linkedin_urls)
        assert len(listings) == 1
        assert listings[0].source == "linkedin"

    def test_skips_linkedin_actor_without_urls(self):
        mock_client, mock_actor = self._mock_apify_client([SAMPLE_APIFY_ITEM])

        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["hKByXkMQaC5Qt9UMN"],
            client=mock_client,
        )
        listings = provider.search_jobs("engineer")
        assert listings == []
        mock_client.actor.assert_not_called()
        mock_actor.call.assert_not_called()

    def test_returns_empty_without_token(self):
        provider = ApifyJobsProvider(api_token="", actor_ids=["actor"])
        assert provider.search_jobs("query") == []

    def test_search_jobs_handles_explicit_none_max_items(self):
        """Regression: max_items=None must not compare int with None in min()."""
        mock_client, mock_actor = self._mock_apify_client([SAMPLE_LINKEDIN_APIFY_ITEM])
        linkedin_urls = [
            "https://www.linkedin.com/jobs/search/?keywords=backend&location=India&f_WT=2&f_E=3%2C4"
        ]
        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["hKByXkMQaC5Qt9UMN"],
            max_results=50,
            client=mock_client,
        )
        listings = provider.search_jobs(
            "backend engineer",
            location="Remote",
            urls=linkedin_urls,
            max_items=None,
        )
        assert len(listings) == 1
        run_input = mock_actor.call.call_args.kwargs["run_input"]
        assert run_input["count"] == 50

    def test_actor_failure_records_last_search_errors(self):
        mock_client = MagicMock()
        mock_actor = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.side_effect = RuntimeError("Input is not valid")

        provider = ApifyJobsProvider(
            api_token="test-token",
            actor_ids=["hKByXkMQaC5Qt9UMN"],
            client=mock_client,
        )
        linkedin_urls = [
            "https://www.linkedin.com/jobs/search/?keywords=backend&location=India&f_WT=2&f_E=3%2C4"
        ]
        listings = provider.search_jobs("backend", urls=linkedin_urls)
        assert listings == []
        assert len(provider.last_search_errors) == 1
        assert "Input is not valid" in provider.last_search_errors[0]


@pytest.mark.django_db
class TestTavilyResearch:
    def test_enrich_company_mocked(self):
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "Acme is a B2B software company.",
            "results": [
                {"title": "Acme News", "url": "https://news.example.com", "content": "Product launch"}
            ],
        }

        provider = TavilyCompanyResearchProvider(api_key="tvly-test", client=mock_client)
        result = provider.enrich_company("Acme Corp", job_title="Backend Engineer")
        assert result["available"] is True
        assert result["summary"]
        assert len(result["snippets"]) >= 1
        assert mock_client.search.call_count == len(
            build_research_queries("Acme Corp", "Backend Engineer")
        )
        first_query = mock_client.search.call_args_list[0].kwargs["query"]
        assert "company overview" in first_query

    def test_skips_without_api_key(self):
        provider = TavilyCompanyResearchProvider(api_key="")
        result = provider.enrich_company("Acme")
        assert result["available"] is False


@pytest.mark.django_db
class TestJobSearchService:
    def test_search_passes_linkedin_urls_to_apify(self, user, workflow):
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = []
        mock_apify.actor_ids = ["hKByXkMQaC5Qt9UMN"]
        mock_apify.api_token = "test-token"
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        context = {
            "goal": "Senior Software Engineer Python JavaScript HTML",
            "preferences": {
                "target_roles": ["Senior Software Engineer"],
                "target_locations": ["Hyderabad"],
                "skills": ["Python", "JavaScript", "HTML"],
            },
        }
        result = service.search(user, workflow, context)
        expected_urls = service.build_linkedin_search_urls(context)
        mock_apify.search_jobs.assert_called_once_with(
            "Senior Software Engineer",
            location="Hyderabad",
            urls=expected_urls,
            split_country="IN",
        )
        assert result["provider_summary"]["providers"]["apify"]["configured"] is True
        assert result["provider_summary"]["linkedin_urls"] == expected_urls

    def test_search_marks_apify_unconfigured_when_token_missing(self, user, workflow):
        mock_apify = MagicMock()
        mock_apify.api_token = ""
        mock_apify.actor_ids = ["hKByXkMQaC5Qt9UMN"]
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        result = service.search(
            user,
            workflow,
            {"goal": "find jobs", "preferences": {"target_roles": ["Engineer"]}},
        )
        mock_apify.search_jobs.assert_not_called()
        assert result["provider_summary"]["providers"]["apify"]["configured"] is False
        assert result["provider_summary"]["providers"]["apify"]["status"] == "skipped"

    def test_deduplicates_and_persists(self, user, workflow):
        listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        duplicate = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")

        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing, duplicate]
        mock_apify.actor_ids = ["linkedin/jobs-scraper"]
        mock_apify.api_token = "test-token"

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
        assert not job.company_research.get("available")
        mock_tavily.enrich_jobs.assert_not_called()
        assert result["provider_summary"]["providers"]["tavily_research"]["status"] == "deferred"

    def test_rerun_skips_existing_user_job(self, user, workflow):
        listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["linkedin/jobs-scraper"]
        mock_apify.api_token = "test-token"
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        context = {
            "goal": "Find backend roles",
            "preferences": {"target_roles": ["Backend Engineer"]},
        }
        first = service.search(user, workflow, context)
        assert first["discovered_count"] == 1
        second = service.search(user, workflow, context)
        assert second["discovered_count"] == 0
        assert Job.objects.count() == 1
        assert Opportunity.objects.filter(user=user).count() == 1

    def test_cross_workflow_no_duplicate_opportunity(self, user):
        listing = normalize_apify_item(SAMPLE_APIFY_ITEM, source="linkedin")
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["linkedin/jobs-scraper"]
        mock_apify.api_token = "test-token"
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        context = {"goal": "Find roles", "preferences": {"target_roles": ["Engineer"]}}
        workflow_a = WorkflowExecution.objects.create(
            user=user, name="A", goal="A", status="completed"
        )
        workflow_b = WorkflowExecution.objects.create(
            user=user, name="B", goal="B", status="completed"
        )
        service.search(user, workflow_a, context)
        result = service.search(user, workflow_b, context)
        assert result["discovered_count"] == 0
        assert Opportunity.objects.filter(user=user).count() == 1

    def test_dedupe_by_apply_url_when_external_id_differs(self, user, workflow):
        base_url = "https://example.com/jobs/123"
        listing_a = normalize_apify_item(
            {**SAMPLE_APIFY_ITEM, "id": "id-a", "url": base_url},
            source="linkedin",
        )
        listing_b = normalize_apify_item(
            {**SAMPLE_APIFY_ITEM, "id": "id-b", "url": f"{base_url}?utm=1"},
            source="linkedin",
        )
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing_a, listing_b]
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        result = service.search(
            user,
            workflow,
            {"goal": "test", "preferences": {"target_roles": ["Engineer"]}},
        )
        assert result["discovered_count"] == 1
        assert Job.objects.count() == 1


@pytest.mark.django_db
class TestJobSearchAgent:
    def test_zero_results_summary_suggests_profile_when_apify_configured(self, user, workflow):
        mock_service = MagicMock()
        mock_service.search.return_value = {
            "query": "Senior Software Engineer",
            "location": "Hyderabad",
            "discovered_count": 0,
            "total_listings": 0,
            "provider_summary": {
                "providers": {
                    "apify": {"count": 0, "status": "completed", "configured": True},
                    "tavily_research": {"companies_enriched": 0, "status": "completed"},
                },
                "errors": [],
            },
            "errors": [],
            "opportunities": [],
        }

        agent = JobSearchAgent(search_service=mock_service)
        result = agent.search(user, workflow, {"goal": "find jobs", "preferences": {}})
        summary = result["reasoning_summary"]
        assert "0 opportunities" in summary
        assert "target roles" in summary.lower()
        assert "APIFY_API_TOKEN" not in summary

    def test_zero_results_summary_suggests_apify_config_when_not_configured(
        self, user, workflow
    ):
        mock_service = MagicMock()
        mock_service.search.return_value = {
            "query": "Senior Software Engineer",
            "location": "Hyderabad",
            "discovered_count": 0,
            "total_listings": 0,
            "provider_summary": {
                "providers": {
                    "apify": {"count": 0, "status": "skipped", "configured": False},
                    "tavily_research": {"companies_enriched": 0, "status": "completed"},
                },
                "errors": [],
            },
            "errors": [],
            "opportunities": [],
        }

        agent = JobSearchAgent(search_service=mock_service)
        result = agent.search(user, workflow, {"goal": "find jobs", "preferences": {}})
        summary = result["reasoning_summary"]
        assert "APIFY_API_TOKEN" in summary

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
        workflow = service.repo.create(
            user=user,
            name="Find backend engineer roles",
            goal="Find backend engineer roles",
            status="running",
        )
        result = service.execute_workflow(user, workflow, goal="Find backend engineer roles")
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
        Opportunity.objects.create(
            user=user,
            job=job,
            workflow_execution=workflow,
            match_score=80,
        )

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("opportunity-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["opportunities"]) == 1
        assert response.data["opportunities"][0]["job"]["title"] == "Engineer"

    def test_detail_not_found(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("opportunity-detail", kwargs={"opportunity_id": "00000000-0000-0000-0000-000000000001"})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_workflow_job_search_rerun(self, api_client, user, workflow):
        api_client.force_authenticate(user=user)
        with patch("apps.workflows.services.dispatch_rerun_job_search") as mock_dispatch:
            response = api_client.post(
                reverse("workflow-job-search", kwargs={"workflow_id": workflow.id})
            )
        assert response.status_code == status.HTTP_200_OK
        mock_dispatch.assert_called_once()
        assert response.data["dispatched"] is True
        assert response.data["status"] == "running"
        workflow.refresh_from_db()
        assert workflow.status == "running"
