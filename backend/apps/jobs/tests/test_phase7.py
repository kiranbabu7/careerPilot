"""Phase 7 tests — applications, interview prep, and APIs."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.interview_prep import INTERVIEW_PREP_AGENT_NAME, InterviewPrepAgent
from apps.agents.models import AgentExecution
from apps.applications.interview_provider import InterviewPlanGenerationResult, InterviewPrepProvider
from apps.applications.models import (
    Application,
    ApplicationStage,
    ApplicationStageEvent,
    InterviewPlan,
)
from apps.applications.repositories import ApplicationRepository
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.tests.test_phase2 import user
from apps.users.models import User
from apps.workflows.models import WorkflowExecution


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com",
        password="pass12345",
        first_name="Other",
        last_name="User",
    )


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
        external_id="ext-phase7",
        source="linkedin",
        title="Staff Backend Engineer",
        company="Globex Corp",
        location="Remote",
        is_remote=True,
        description="Python Django PostgreSQL system design leadership",
        dedupe_key="dedupe-globex-phase7",
        company_research={"available": True, "summary": "Globex is scaling platform teams."},
    )


@pytest.fixture
def opportunity(user, workflow, job):
    return Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.SAVED,
        match_score=88,
        evaluation={
            "match_score": 88,
            "recommendation": "strong_match",
            "rationale": "Strong backend alignment.",
            "strengths": ["Python", "Django"],
            "gaps": ["Staff-level scope examples"],
        },
    )


@pytest.mark.django_db
class TestApplicationModel:
    def test_create_from_opportunity(self, user, opportunity):
        application, created = ApplicationRepository().create_from_opportunity(
            user, opportunity
        )
        assert created is True
        assert application.stage == ApplicationStage.APPLIED
        assert application.applied_at is not None
        opportunity.refresh_from_db()
        assert opportunity.status == OpportunityStatus.APPLIED

    def test_one_per_user_opportunity(self, user, opportunity):
        repo = ApplicationRepository()
        first, created_first = repo.create_from_opportunity(user, opportunity)
        second, created_second = repo.create_from_opportunity(user, opportunity)
        assert created_first is True
        assert created_second is False
        assert first.id == second.id
        assert Application.objects.filter(user=user, opportunity=opportunity).count() == 1

    def test_stage_update_records_history(self, user, opportunity):
        application, _ = ApplicationRepository().create_from_opportunity(user, opportunity)
        ApplicationRepository().update(
            application,
            stage=ApplicationStage.INTERVIEWING,
            stage_notes="Phone screen scheduled",
        )
        events = list(application.stage_events.order_by("-created_at"))
        assert len(events) == 2
        assert events[0].from_stage == ApplicationStage.APPLIED
        assert events[0].to_stage == ApplicationStage.INTERVIEWING
        assert events[0].notes == "Phone screen scheduled"


@pytest.mark.django_db
class TestApplicationAPI:
    def test_create_from_opportunity_endpoint(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        url = reverse(
            "application-create-from-opportunity",
            kwargs={"opportunity_id": opportunity.id},
        )
        response = api_client.post(url)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["created"] is True
        assert response.data["application"]["stage"] == "applied"

    def test_create_is_idempotent(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        url = reverse(
            "application-create-from-opportunity",
            kwargs={"opportunity_id": opportunity.id},
        )
        api_client.post(url)
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["created"] is False

    def test_kanban_list_groups_by_stage(self, api_client, user, opportunity):
        ApplicationRepository().create_from_opportunity(user, opportunity)
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("application-list"))
        assert response.status_code == status.HTTP_200_OK
        assert "stages" in response.data
        assert len(response.data["stages"]["applied"]) == 1

    def test_patch_stage(self, api_client, user, opportunity):
        application, _ = ApplicationRepository().create_from_opportunity(user, opportunity)
        api_client.force_authenticate(user=user)
        url = reverse("application-detail", kwargs={"application_id": application.id})
        response = api_client.patch(
            url,
            {"stage": "interviewing", "stage_notes": "Onsite next week"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["stage"] == "interviewing"
        assert ApplicationStageEvent.objects.filter(application=application).count() == 2

    def test_ownership_isolation(self, api_client, user, other_user, opportunity):
        application, _ = ApplicationRepository().create_from_opportunity(user, opportunity)
        api_client.force_authenticate(user=other_user)
        url = reverse("application-detail", kwargs={"application_id": application.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestInterviewPrepAgent:
    def test_generates_plan_with_fallback(self, user, opportunity):
        provider = MagicMock(spec=InterviewPrepProvider)
        provider.generate.return_value = InterviewPlanGenerationResult(
            content={
                "prep_roadmap": ["Step 1"],
                "likely_questions": ["Why this role?"],
                "system_design_topics": ["API design"],
                "company_talking_points": ["Mission fit"],
                "resume_stories": ["STAR story"],
                "gaps_to_practice": ["Staff scope"],
                "day_by_day_checklist": [{"day": 1, "tasks": ["Review JD"]}],
            },
            markdown="# Interview Prep Plan",
            model_name="local-fallback",
            used_fallback=True,
        )

        agent = InterviewPrepAgent(provider=provider)
        result = agent.generate(user, opportunity)

        assert result["plan"].opportunity_id == opportunity.id
        assert result["plan"].content["likely_questions"]
        assert result["execution"].agent_name == INTERVIEW_PREP_AGENT_NAME
        assert result["execution"].status == "completed"
        assert AgentExecution.objects.filter(
            user=user, agent_name=INTERVIEW_PREP_AGENT_NAME
        ).exists()

    def test_opportunity_interview_prep_api(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        url = reverse(
            "opportunity-interview-prep",
            kwargs={"opportunity_id": opportunity.id},
        )
        with patch.object(InterviewPrepAgent, "generate") as mock_generate:
            plan = InterviewPlan.objects.create(
                user=user,
                opportunity=opportunity,
                prompt_name="interview_prep",
                prompt_version=1,
                model_name="local-fallback",
                content={"prep_roadmap": ["Review JD"]},
                markdown="# Plan",
            )
            execution = AgentExecution.objects.create(
                user=user,
                agent_name=INTERVIEW_PREP_AGENT_NAME,
                status="completed",
            )
            mock_generate.return_value = {
                "plan": plan,
                "execution": execution,
                "reasoning_summary": "Prep plan created.",
            }
            response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["interview_plan"]["id"] == str(plan.id)

    def test_application_interview_prep_api(self, api_client, user, opportunity):
        application, _ = ApplicationRepository().create_from_opportunity(user, opportunity)
        api_client.force_authenticate(user=user)
        url = reverse(
            "application-interview-prep",
            kwargs={"application_id": application.id},
        )
        with patch.object(InterviewPrepAgent, "generate") as mock_generate:
            plan = InterviewPlan.objects.create(
                user=user,
                opportunity=opportunity,
                application=application,
                prompt_name="interview_prep",
                prompt_version=1,
                model_name="local-fallback",
                content={"prep_roadmap": ["Practice stories"]},
                markdown="# Plan",
            )
            execution = AgentExecution.objects.create(
                user=user,
                agent_name=INTERVIEW_PREP_AGENT_NAME,
                status="completed",
            )
            mock_generate.return_value = {
                "plan": plan,
                "execution": execution,
                "reasoning_summary": "Application prep plan.",
            }
            response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["interview_plan"]["application_id"] == str(application.id)

    def test_interview_list_and_detail(self, api_client, user, opportunity):
        plan = InterviewPlan.objects.create(
            user=user,
            opportunity=opportunity,
            prompt_name="interview_prep",
            prompt_version=1,
            model_name="local-fallback",
            content={"likely_questions": ["Tell me about yourself"]},
            markdown="# Plan",
        )
        api_client.force_authenticate(user=user)
        list_response = api_client.get(reverse("interview-list"))
        assert list_response.status_code == status.HTTP_200_OK
        all_plans = (
            list_response.data.get("active", [])
            + list_response.data.get("upcoming", [])
            + list_response.data.get("recent", [])
        )
        assert any(item["id"] == str(plan.id) for item in all_plans)

        detail_response = api_client.get(
            reverse("interview-detail", kwargs={"interview_id": plan.id})
        )
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["content"]["likely_questions"]

    def test_provider_local_fallback(self):
        provider = InterviewPrepProvider()
        with patch.object(provider, "_ai_configured", return_value=False):
            result = provider.generate(
                "Title: Backend Engineer\nCompany: Acme\n"
                "## Match evaluation\nGaps: Kubernetes; system design\n"
            )
        assert result.used_fallback is True
        assert result.content["prep_roadmap"]
        assert result.content["gaps_to_practice"]
