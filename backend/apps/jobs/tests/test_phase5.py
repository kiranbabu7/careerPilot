"""Phase 5 tests — evaluation, company research, APIs, workflow integration."""

from unittest.mock import MagicMock

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.company_research import COMPANY_RESEARCH_AGENT_NAME, CompanyResearchAgent
from apps.agents.job_evaluation import JOB_EVALUATION_AGENT_NAME, JobEvaluationAgent
from apps.agents.models import AgentExecution
from apps.jobs.evaluation import (
    BORDERLINE_MATCH_THRESHOLD,
    HIGH_MATCH_THRESHOLD,
    evaluate_opportunity,
)
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.jobs.repositories import OpportunityRepository
from apps.providers.jobs.company_research_synthesis import build_research_queries
from apps.providers.jobs.tavily_research import TavilyCompanyResearchProvider
from apps.resumes.tests.test_phase2 import user
from apps.users.models import UserPreference
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


@pytest.fixture
def job():
    return Job.objects.create(
        external_id="ext-1",
        source="linkedin",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        salary_min=130000,
        salary_max=170000,
        description="Python Django PostgreSQL AWS Kubernetes",
        dedupe_key="dedupe-acme-1",
        company_research={"available": True, "summary": "Acme is growing."},
    )


@pytest.fixture
def opportunity(user, workflow, job):
    return Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.DISCOVERED,
    )


@pytest.fixture
def preferences(user):
    pref, _ = UserPreference.objects.get_or_create(user=user)
    pref.target_roles = ["Senior Backend Engineer", "Staff Engineer"]
    pref.target_locations = ["Remote"]
    pref.remote_preference = "remote"
    pref.skills = ["Python", "Django", "PostgreSQL", "AWS"]
    pref.salary_min = 120000
    pref.salary_max = 200000
    pref.save()
    return pref


class TestEvaluateOpportunity:
    def test_high_match_for_aligned_role_and_skills(self):
        result = evaluate_opportunity(
            job_title="Senior Backend Engineer",
            job_description="Python Django PostgreSQL AWS",
            job_location="Remote",
            is_remote=True,
            salary_min=130000,
            salary_max=170000,
            company_research={"available": True, "summary": "Growing team"},
            preferences={
                "target_roles": ["Senior Backend Engineer"],
                "skills": ["Python", "Django", "PostgreSQL"],
                "target_locations": ["Remote"],
                "remote_preference": "remote",
                "salary_min": 120000,
                "salary_max": 200000,
            },
        )
        assert result["match_score"] >= 80
        assert result["recommendation"] in ("strong_match", "good_match")
        assert len(result["strengths"]) >= 2
        assert "factors" in result

    def test_good_role_fit_passes_threshold_without_company_research(self):
        """Real listings often lack Tavily enrichment; role fit should still surface."""
        result = evaluate_opportunity(
            job_title="Senior Backend Engineer",
            job_description="Python Django PostgreSQL AWS Kubernetes",
            job_location="Remote",
            is_remote=True,
            salary_min=130000,
            salary_max=170000,
            company_research={},
            preferences={
                "target_roles": ["Senior Backend Engineer"],
                "skills": ["Python", "Django", "PostgreSQL"],
                "target_locations": ["Remote"],
                "remote_preference": "remote",
                "salary_min": 120000,
                "salary_max": 200000,
            },
        )
        assert result["match_score"] >= HIGH_MATCH_THRESHOLD

    def test_company_research_factor_uses_existing_json(self):
        research = {
            "available": True,
            "company": "Acme Corp",
            "summary": "Acme Corp is a fast-growing fintech platform.",
            "what_they_do": "Payment processing for SMBs",
        }
        result = evaluate_opportunity(
            job_title="Senior Backend Engineer",
            job_description="Python Django PostgreSQL AWS",
            job_location="Remote",
            is_remote=True,
            salary_min=130000,
            salary_max=170000,
            company_research=research,
            preferences={
                "target_roles": ["Senior Backend Engineer"],
                "skills": ["Python", "Django"],
                "target_locations": ["Remote"],
                "remote_preference": "remote",
            },
        )
        factor = result["factors"]["company_research"]
        assert factor["score"] == 100
        assert "Acme Corp" in factor["detail"]
        assert "No company research available yet" not in factor["detail"]

    def test_company_research_factor_without_available_flag(self):
        """Legacy or partial payloads with content should not score neutral."""
        research = {
            "summary": "Globex is scaling platform teams.",
            "what_they_do": "Enterprise SaaS",
        }
        result = evaluate_opportunity(
            job_title="Staff Engineer",
            job_description="Go distributed systems",
            job_location="Remote",
            is_remote=True,
            salary_min=None,
            salary_max=None,
            company_research=research,
            preferences={"target_roles": ["Staff Engineer"], "skills": ["Go"]},
        )
        factor = result["factors"]["company_research"]
        assert factor["score"] == 100
        assert "Globex" in factor["detail"]

    def test_company_stage_scoring_with_dict_snippets(self):
        """Regression: snippet payloads are dicts, not joinable strings."""
        research = {
            "available": True,
            "summary": "Series B fintech startup expanding engineering.",
            "snippets": [
                {
                    "title": "Funding news",
                    "url": "https://example.com/funding",
                    "snippet": "Raised Series B to scale growth-stage platform.",
                    "category": "funding",
                }
            ],
        }
        result = evaluate_opportunity(
            job_title="Senior Backend Engineer",
            job_description="Python Django PostgreSQL",
            job_location="Remote",
            is_remote=True,
            salary_min=130000,
            salary_max=170000,
            company_research=research,
            preferences={
                "target_roles": ["Senior Backend Engineer"],
                "skills": ["Python", "Django"],
                "target_locations": ["Remote"],
                "remote_preference": "remote",
            },
            planner_constraints={"company_stage": "growth-stage startup"},
        )
        factor = result["factors"]["company_research"]
        assert factor["score"] >= 80
        assert "growth-stage startup" in factor["detail"]

    def test_low_match_for_mismatched_role(self):
        result = evaluate_opportunity(
            job_title="Marketing Manager",
            job_description="Brand campaigns and social media",
            job_location="New York, NY",
            is_remote=False,
            salary_min=60000,
            salary_max=80000,
            company_research={},
            preferences={
                "target_roles": ["Senior Backend Engineer"],
                "skills": ["Python", "Django"],
                "target_locations": ["Remote"],
                "remote_preference": "remote",
                "salary_min": 150000,
            },
        )
        assert result["match_score"] < BORDERLINE_MATCH_THRESHOLD
        assert len(result["gaps"]) >= 1


@pytest.mark.django_db
class TestJobEvaluationAgent:
    def test_evaluates_and_persists(self, user, opportunity, preferences):
        agent = JobEvaluationAgent()
        result = agent.evaluate(user, opportunity)

        opportunity.refresh_from_db()
        assert opportunity.match_score is not None
        assert opportunity.match_score == result["match_score"]
        assert opportunity.evaluation["recommendation"]
        assert AgentExecution.objects.filter(agent_name=JOB_EVALUATION_AGENT_NAME).exists()

    def test_batch_evaluation(self, user, workflow, job, preferences):
        opp2_job = Job.objects.create(
            external_id="ext-2",
            source="linkedin",
            title="Staff Engineer",
            company="Beta Inc",
            location="Remote",
            is_remote=True,
            description="Python Go distributed systems",
            dedupe_key="dedupe-beta-1",
        )
        opp1 = Opportunity.objects.create(user=user, job=job, workflow_execution=workflow)
        opp2 = Opportunity.objects.create(user=user, job=opp2_job, workflow_execution=workflow)

        agent = JobEvaluationAgent()
        batch = agent.evaluate_batch(user, [opp1, opp2], workflow=workflow)
        assert batch["evaluated_count"] == 2
        assert batch["top_match_score"] > 0
        assert (
            batch["accepted_count"]
            + batch["borderline_count"]
            + batch["rejected_count"]
            == batch["evaluated_count"]
        )
        assert (
            AgentExecution.objects.filter(agent_name=JOB_EVALUATION_AGENT_NAME).count()
            == 1
        )

    def test_auto_rejects_low_match(self, user, workflow, preferences):
        low_job = Job.objects.create(
            external_id="ext-low",
            source="linkedin",
            title="Marketing Manager",
            company="Retail Co",
            location="New York, NY",
            description="Brand campaigns",
            dedupe_key="dedupe-low-1",
        )
        opp = Opportunity.objects.create(
            user=user, job=low_job, workflow_execution=workflow
        )
        agent = JobEvaluationAgent()
        result = agent.evaluate(user, opp, workflow=workflow)
        opp.refresh_from_db()
        assert result["match_score"] < BORDERLINE_MATCH_THRESHOLD
        assert opp.status == OpportunityStatus.REJECTED

    def test_keeps_discovered_for_high_match(self, user, opportunity, preferences):
        agent = JobEvaluationAgent()
        result = agent.evaluate(user, opportunity)
        opportunity.refresh_from_db()
        assert result["match_score"] >= HIGH_MATCH_THRESHOLD
        assert opportunity.status == OpportunityStatus.DISCOVERED


@pytest.mark.django_db
class TestCompanyResearchAgent:
    def test_research_persists_to_job(self, user, opportunity):
        mock_tavily = MagicMock()
        mock_tavily.enrich_company.return_value = {
            "available": True,
            "company": "Acme Corp",
            "summary": "Acme is hiring engineers.",
            "snippets": [{"title": "News", "url": "https://example.com", "snippet": "Hiring"}],
        }

        agent = CompanyResearchAgent(tavily_provider=mock_tavily)
        result = agent.research(user, opportunity)

        opportunity.job.refresh_from_db()
        assert opportunity.job.company_research["available"] is True
        assert "hiring" in opportunity.job.company_research["summary"].lower()
        assert AgentExecution.objects.filter(agent_name=COMPANY_RESEARCH_AGENT_NAME).exists()
        assert result["company_research"]["available"] is True

    def test_research_after_eval_updates_stale_factor(self, user, opportunity, preferences):
        opportunity.job.company_research = {}
        opportunity.job.save(update_fields=["company_research"])

        eval_agent = JobEvaluationAgent()
        eval_agent.evaluate(user, opportunity)
        opportunity.refresh_from_db()
        assert opportunity.evaluation["factors"]["company_research"]["score"] == 50
        assert "No company research available yet" in (
            opportunity.evaluation["factors"]["company_research"]["detail"]
        )

        mock_tavily = MagicMock()
        mock_tavily.enrich_company.return_value = {
            "available": True,
            "company": "Acme Corp",
            "summary": "Acme is hiring engineers and expanding platform teams.",
            "snippets": [{"title": "News", "url": "https://example.com", "snippet": "Hiring"}],
        }

        research_agent = CompanyResearchAgent(tavily_provider=mock_tavily)
        research_agent.research(user, opportunity)

        opportunity.refresh_from_db()
        factor = opportunity.evaluation["factors"]["company_research"]
        assert factor["score"] == 100
        assert "Acme is hiring" in factor["detail"]
        assert opportunity.match_score > 50

    def test_unavailable_provider_graceful(self, user, opportunity):
        mock_tavily = MagicMock()
        mock_tavily.enrich_company.return_value = {
            "available": False,
            "reason": "not_configured",
        }

        agent = CompanyResearchAgent(tavily_provider=mock_tavily)
        result = agent.research(user, opportunity)

        execution = AgentExecution.objects.get(agent_name=COMPANY_RESEARCH_AGENT_NAME)
        assert execution.status == "completed"
        assert result["company_research"]["available"] is False

    def test_tavily_401_returns_unavailable(self):
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("401 Unauthorized")

        provider = TavilyCompanyResearchProvider(
            api_key="tvly-test",
            client=mock_client,
        )
        result = provider.enrich_company("Acme Corp")
        assert result["available"] is False
        assert result["reason"] == "auth_error"
        assert "401" in result["error"]
        assert mock_client.search.call_count >= len(build_research_queries("Acme Corp"))

    def test_tavily_missing_key_returns_not_configured(self):
        provider = TavilyCompanyResearchProvider(api_key="")
        result = provider.enrich_company("Acme Corp")
        assert result["available"] is False
        assert result["reason"] == "not_configured"

    def test_tavily_maps_client_response(self):
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "Acme is a software company building analytics tools.",
            "results": [
                {
                    "title": "Acme News",
                    "url": "https://example.com/acme",
                    "content": "Acme expanded its product portfolio.",
                }
            ],
        }
        provider = TavilyCompanyResearchProvider(
            api_key="tvly-test",
            client=mock_client,
        )
        result = provider.enrich_company("Acme Corp", job_title="Engineer")
        assert result["available"] is True
        assert result["company"] == "Acme Corp"
        assert result["summary"]
        assert "snippets" in result
        assert len(result["snippets"]) >= 1
        assert mock_client.search.call_count == len(build_research_queries("Acme Corp", "Engineer"))


@pytest.mark.django_db
class TestPhase5APIs:
    def test_list_returns_high_match_and_borderline(self, api_client, user, workflow):
        high_job = Job.objects.create(
            external_id="high-1",
            source="linkedin",
            title="Senior Backend Engineer",
            company="Acme",
            dedupe_key="dedupe-high",
        )
        borderline_job = Job.objects.create(
            external_id="border-1",
            source="linkedin",
            title="Backend Engineer",
            company="Beta",
            dedupe_key="dedupe-border",
        )
        low_job = Job.objects.create(
            external_id="low-1",
            source="linkedin",
            title="Marketing Manager",
            company="Retail",
            dedupe_key="dedupe-low",
        )
        uneval_job = Job.objects.create(
            external_id="uneval-1",
            source="linkedin",
            title="Pending Role",
            company="Pending Co",
            dedupe_key="dedupe-uneval",
        )
        Opportunity.objects.create(
            user=user,
            job=high_job,
            workflow_execution=workflow,
            match_score=85,
            status=OpportunityStatus.DISCOVERED,
        )
        Opportunity.objects.create(
            user=user,
            job=borderline_job,
            workflow_execution=workflow,
            match_score=62,
            status=OpportunityStatus.DISCOVERED,
        )
        Opportunity.objects.create(
            user=user,
            job=low_job,
            workflow_execution=workflow,
            match_score=40,
            status=OpportunityStatus.REJECTED,
        )
        Opportunity.objects.create(
            user=user,
            job=uneval_job,
            workflow_execution=workflow,
            match_score=None,
        )

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("opportunity-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["high_match_threshold"] == HIGH_MATCH_THRESHOLD
        assert response.data["borderline_match_threshold"] == BORDERLINE_MATCH_THRESHOLD
        assert response.data["pending_evaluation_count"] == 1
        titles = {o["job"]["title"] for o in response.data["opportunities"]}
        assert titles == {"Senior Backend Engineer", "Backend Engineer"}

    def test_list_includes_last_search_summary(self, api_client, user, workflow):
        workflow.result = {
            "discovered_count": 5,
            "evaluated_count": 5,
            "accepted_count": 0,
            "borderline_count": 2,
            "rejected_count": 3,
            "top_match_score": 65,
        }
        workflow.status = "completed"
        workflow.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("opportunity-list"))
        summary = response.data["last_search_summary"]
        assert summary is not None
        assert summary["discovered_count"] == 5
        assert summary["accepted_count"] == 0
        assert summary["borderline_count"] == 2
        assert summary["rejected_count"] == 3
        assert summary["top_match_score"] == 65

    def test_list_include_rejected(self, api_client, user, workflow):
        job = Job.objects.create(
            external_id="rej-1",
            source="linkedin",
            title="Rejected Role",
            company="Co",
            dedupe_key="dedupe-rej",
        )
        Opportunity.objects.create(
            user=user,
            job=job,
            workflow_execution=workflow,
            match_score=30,
            status=OpportunityStatus.REJECTED,
        )
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("opportunity-list"), {"include_rejected": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["opportunities"]) == 1

    def test_list_filters_by_workflow_high_match(self, api_client, user, workflow):
        other_workflow = WorkflowExecution.objects.create(
            user=user,
            goal="Other search",
            status="completed",
        )
        high_job = Job.objects.create(
            external_id="wf-high-1",
            source="linkedin",
            title="Workflow High Match",
            company="Acme",
            dedupe_key="dedupe-wf-high",
        )
        borderline_job = Job.objects.create(
            external_id="wf-border-1",
            source="linkedin",
            title="Workflow Borderline",
            company="Beta",
            dedupe_key="dedupe-wf-border",
        )
        other_job = Job.objects.create(
            external_id="other-high-1",
            source="linkedin",
            title="Other Workflow Match",
            company="Gamma",
            dedupe_key="dedupe-other-high",
        )
        Opportunity.objects.create(
            user=user,
            job=high_job,
            workflow_execution=workflow,
            match_score=85,
            status=OpportunityStatus.DISCOVERED,
        )
        Opportunity.objects.create(
            user=user,
            job=borderline_job,
            workflow_execution=workflow,
            match_score=62,
            status=OpportunityStatus.DISCOVERED,
        )
        Opportunity.objects.create(
            user=user,
            job=other_job,
            workflow_execution=other_workflow,
            match_score=90,
            status=OpportunityStatus.DISCOVERED,
        )

        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("opportunity-list"),
            {"workflow_id": str(workflow.id), "filter": "high_match"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["workflow_execution_id"] == str(workflow.id)
        titles = {o["job"]["title"] for o in response.data["opportunities"]}
        assert titles == {"Workflow High Match"}

    def test_list_filters_by_workflow_all_includes_non_high_match(self, api_client, user, workflow):
        borderline_job = Job.objects.create(
            external_id="wf-border-only-1",
            source="linkedin",
            title="Workflow Borderline Only",
            company="Beta",
            dedupe_key="dedupe-wf-border-only",
        )
        rejected_job = Job.objects.create(
            external_id="wf-rejected-1",
            source="linkedin",
            title="Workflow Rejected",
            company="Gamma",
            dedupe_key="dedupe-wf-rejected",
        )
        Opportunity.objects.create(
            user=user,
            job=borderline_job,
            workflow_execution=workflow,
            match_score=62,
            status=OpportunityStatus.DISCOVERED,
        )
        Opportunity.objects.create(
            user=user,
            job=rejected_job,
            workflow_execution=workflow,
            match_score=30,
            status=OpportunityStatus.REJECTED,
        )

        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("opportunity-list"),
            {"workflow_id": str(workflow.id), "filter": "all"},
        )
        assert response.status_code == status.HTTP_200_OK
        titles = {o["job"]["title"] for o in response.data["opportunities"]}
        assert titles == {"Workflow Borderline Only", "Workflow Rejected"}

    def test_list_workflow_filter_not_found(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("opportunity-list"),
            {"workflow_id": "00000000-0000-0000-0000-000000000001"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_status_saved(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            reverse("opportunity-detail", kwargs={"opportunity_id": opportunity.id}),
            {"status": "saved"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "saved"
        opportunity.refresh_from_db()
        assert opportunity.status == OpportunityStatus.SAVED

    def test_patch_status_rejected(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            reverse("opportunity-detail", kwargs={"opportunity_id": opportunity.id}),
            {"status": "rejected"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "rejected"

    def test_evaluate_endpoint(self, api_client, user, opportunity, preferences):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse("opportunity-evaluate", kwargs={"opportunity_id": opportunity.id}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert "match_score" in response.data
        assert response.data["match_score"] > 0
        assert "agent_execution" in response.data

    def test_research_company_endpoint(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        with pytest.MonkeyPatch.context() as mp:
            mock_tavily = MagicMock()
            mock_tavily.enrich_company.return_value = {
                "available": True,
                "summary": "Test summary",
                "snippets": [],
            }
            mp.setattr(
                "apps.jobs.views.CompanyResearchAgent",
                lambda: CompanyResearchAgent(tavily_provider=mock_tavily),
            )
            response = api_client.post(
                reverse(
                    "opportunity-research-company",
                    kwargs={"opportunity_id": opportunity.id},
                ),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["company_research"]["available"] is True

    def test_companies_list(self, api_client, user, opportunity):
        opportunity.match_score = 85
        opportunity.save(update_fields=["match_score"])
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("company-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Acme Corp"
        assert response.data[0]["opportunity_count"] == 1

    def test_auth_isolation(self, api_client, user, opportunity):
        other_user = user.__class__.objects.create_user(
            email="other@example.com",
            password="pass12345",
            first_name="Other",
            last_name="User",
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.patch(
            reverse("opportunity-detail", kwargs={"opportunity_id": opportunity.id}),
            {"status": "saved"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response = api_client.post(
            reverse("opportunity-evaluate", kwargs={"opportunity_id": opportunity.id}),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestWorkflowEvaluationIntegration:
    def test_start_workflow_evaluates_opportunities(self, user, preferences):
        from apps.agents.job_search import JobSearchAgent
        from apps.jobs.services import JobSearchService
        from apps.providers.jobs.normalization import normalize_apify_item

        sample = {
            "id": "job-99",
            "title": "Senior Backend Engineer",
            "companyName": "Acme Corp",
            "location": "Remote",
            "description": "Python Django PostgreSQL",
            "isRemote": True,
            "salaryMin": 130000,
            "salaryMax": 170000,
        }
        listing = normalize_apify_item(sample, source="linkedin")

        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
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
            name="Find backend roles",
            goal="Find backend roles",
            status="running",
        )
        result = service.execute_workflow(user, workflow, goal="Find backend roles")
        assert result["discovered_count"] == 1
        assert result["evaluated_count"] == 1
        assert result["accepted_count"] == 1
        assert result["rejected_count"] == 0
        assert result["top_match_score"] > 0

        opp = Opportunity.objects.filter(user=user).first()
        assert opp.match_score is not None
        assert opp.match_score >= HIGH_MATCH_THRESHOLD
        assert opp.status == OpportunityStatus.DISCOVERED
        assert opp.evaluation.get("recommendation")

    def test_evaluates_all_unevaluated_not_capped(self, user, preferences):
        from apps.agents.job_search import JobSearchAgent
        from apps.jobs.services import JobSearchService
        from apps.providers.jobs.normalization import normalize_apify_item

        listings = []
        for i in range(12):
            sample = {
                "id": f"job-{i}",
                "title": f"Senior Backend Engineer {i}",
                "companyName": f"Company {i}",
                "location": "Remote",
                "description": "Python Django PostgreSQL",
                "isRemote": True,
            }
            listings.append(normalize_apify_item(sample, source="linkedin"))

        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = listings
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
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
            name="Find backend roles",
            goal="Find backend roles",
            status="running",
        )
        result = service.execute_workflow(user, workflow, goal="Find backend roles")
        assert result["discovered_count"] == 12
        assert result["evaluated_count"] == 12
        assert Opportunity.objects.filter(user=user, match_score__isnull=False).count() == 12

    def test_list_shows_high_match_after_workflow_without_company_research(
        self, api_client, user, preferences
    ):
        """Reproduces empty-list bug: jobs without Tavily data must still appear."""
        from apps.agents.job_search import JobSearchAgent
        from apps.jobs.services import JobSearchService
        from apps.providers.jobs.normalization import normalize_apify_item

        listing = normalize_apify_item(
            {
                "id": "job-list-1",
                "title": "Senior Backend Engineer",
                "companyName": "Acme Corp",
                "location": "Remote",
                "description": "Python Django PostgreSQL AWS",
                "isRemote": True,
                "salaryMin": 130000,
                "salaryMax": 170000,
            },
            source="linkedin",
        )
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
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
            name="Find backend roles",
            goal="Find backend roles",
            status="running",
        )
        result = service.execute_workflow(user, workflow, goal="Find backend roles")
        assert result["accepted_count"] >= 1

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("opportunity-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pending_evaluation_count"] == 0
        assert len(response.data["opportunities"]) >= 1

    def test_evaluates_preexisting_unevaluated_on_rerun(self, user, preferences):
        """Reproduces empty-list bug: deduped jobs must still be evaluated."""
        from apps.agents.job_search import JobSearchAgent
        from apps.jobs.services import JobSearchService
        from apps.providers.jobs.normalization import normalize_apify_item

        listing = normalize_apify_item(
            {
                "id": "job-rerun-1",
                "title": "Senior Backend Engineer",
                "companyName": "Acme Corp",
                "location": "Remote",
                "description": "Python Django PostgreSQL",
                "isRemote": True,
                "salaryMin": 130000,
                "salaryMax": 170000,
            },
            source="linkedin",
        )
        job = Job.objects.create(
            external_id="job-rerun-1",
            source="linkedin",
            title=listing.title,
            company=listing.company,
            location=listing.location,
            is_remote=True,
            description=listing.description,
            dedupe_key="existing-dedupe",
        )
        old_workflow = WorkflowExecution.objects.create(
            user=user,
            name="Old workflow",
            goal="Old goal",
            status="completed",
        )
        opp = Opportunity.objects.create(
            user=user,
            job=job,
            workflow_execution=old_workflow,
            match_score=None,
        )

        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
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
        new_workflow = service.repo.create(
            user=user,
            name="New workflow",
            goal="Find backend roles",
            status="running",
        )
        result = service.execute_workflow(user, new_workflow, goal="Find backend roles")
        assert result["evaluated_count"] >= 1

        opp.refresh_from_db()
        assert opp.match_score is not None
        assert Opportunity.objects.filter(user=user).count() == 1

    def test_evaluate_discovered_skips_other_workflows_and_custom_jd(
        self, user, preferences
    ):
        from apps.jobs.models import Job, Opportunity, OpportunityStatus
        from apps.workflows.models import WorkflowExecution
        from apps.workflows.services import WorkflowService

        prep_workflow = WorkflowExecution.objects.create(
            user=user,
            name="Interview prep",
            goal="Prepare for interviews",
            status="completed",
        )
        prep_job = Job.objects.create(
            source="custom",
            title="Senior Software Engineer",
            company="General interview prep",
            description="Interview preparation goal",
            dedupe_key="general-prep",
        )
        prep_opp = Opportunity.objects.create(
            user=user,
            job=prep_job,
            workflow_execution=prep_workflow,
            status=OpportunityStatus.SAVED,
            source_agent="custom_jd",
            match_score=None,
        )

        scheduled_workflow = WorkflowExecution.objects.create(
            user=user,
            name="Scheduled job search",
            goal="Scheduled job search",
            status="running",
        )

        service = WorkflowService()
        summary = service._evaluate_discovered_opportunities(
            user, scheduled_workflow, {"preferences": {}}
        )

        assert summary["evaluated_count"] == 0
        prep_opp.refresh_from_db()
        assert prep_opp.match_score is None


@pytest.mark.django_db
class TestOpportunityRepository:
    def test_list_companies_aggregates(self, user, workflow, job, opportunity):
        opportunity.match_score = 80
        opportunity.save(update_fields=["match_score"])
        repo = OpportunityRepository()
        companies = repo.list_companies_for_user(user)
        assert len(companies) == 1
        assert companies[0]["opportunity_count"] == 1
        assert str(opportunity.id) in companies[0]["opportunity_ids"]


@pytest.mark.django_db
class TestDeferredCompanyResearch:
    def test_job_search_defers_tavily_enrichment(self, user, workflow):
        from apps.jobs.services import JobSearchService
        from apps.providers.jobs.normalization import normalize_apify_item

        sample = {
            "id": "defer-1",
            "title": "Backend Engineer",
            "companyName": "DeferCo",
            "location": "Remote",
            "description": "Python",
            "isRemote": True,
        }
        listing = normalize_apify_item(sample, source="linkedin")
        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
        mock_tavily = MagicMock()

        service = JobSearchService(
            apify_provider=mock_apify,
            tavily_provider=mock_tavily,
        )
        result = service.search(
            user,
            workflow,
            {"goal": "Find backend roles", "preferences": {"target_roles": ["Backend Engineer"]}},
        )

        mock_tavily.enrich_jobs.assert_not_called()
        assert result["provider_summary"]["providers"]["tavily_research"]["status"] == "deferred"
        job = Job.objects.get(company="DeferCo")
        assert not job.company_research.get("available")
