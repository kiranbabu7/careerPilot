"""Tests for external interview tracker."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.interview_prep import INTERVIEW_PREP_AGENT_NAME, InterviewPrepAgent
from apps.agents.models import AgentExecution
from apps.applications.models import (
    Application,
    ApplicationStage,
    Interview,
    InterviewOutcome,
    InterviewPlan,
)
from apps.applications.services import InterviewService
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.tests.test_phase2 import user
from apps.workflows.follow_up import FOLLOW_UP_ADD_INTERVIEW, classify_follow_up
from apps.workflows.models import WorkflowExecution


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def workflow(user):
    return WorkflowExecution.objects.create(
        user=user,
        name="Interview workflow",
        goal="Track interviews",
        status="completed",
    )


@pytest.mark.django_db
class TestInterviewService:
    def test_create_external_builds_pipeline(self, user):
        scheduled_at = timezone.now() + timedelta(days=3)
        interview = InterviewService().create_external(
            user,
            {
                "company": "Acme Corp",
                "job_title": "Staff Engineer",
                "scheduled_at": scheduled_at,
                "round_label": "Technical 1",
                "format": "video",
                "outcome": InterviewOutcome.SCHEDULED,
                "job_description": "Build distributed systems.",
            },
        )

        assert interview.source == "external"
        assert interview.opportunity.job.company == "Acme Corp"
        assert interview.opportunity.job.title == "Staff Engineer"
        assert interview.opportunity.source_agent == "external_interview"
        assert interview.application is not None
        assert interview.application.stage == ApplicationStage.INTERVIEWING
        assert Opportunity.objects.filter(user=user, job=interview.opportunity.job).exists()
        assert Job.objects.filter(source="external_interview").count() == 1

    def test_create_external_requires_company_and_title(self, user):
        with pytest.raises(ValueError, match="company and job_title"):
            InterviewService().create_external(user, {"company": "Acme"})


@pytest.mark.django_db
class TestInterviewAPI:
    def test_create_list_update_and_prep(self, api_client, user):
        api_client.force_authenticate(user=user)
        create_url = reverse("interview-list")
        scheduled_at = (timezone.now() + timedelta(days=2)).isoformat()

        create_response = api_client.post(
            create_url,
            {
                "company": "Globex",
                "job_title": "Backend Engineer",
                "scheduled_at": scheduled_at,
                "round_label": "Phone screen",
                "format": "phone",
                "outcome": "scheduled",
                "job_description": "Python APIs",
            },
            format="json",
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        assert create_response.data["type"] == "scheduled"
        assert create_response.data["job_company"] == "Globex"
        interview_id = create_response.data["id"]

        list_response = api_client.get(create_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert "upcoming_interviews" in list_response.data
        assert any(
            item["id"] == interview_id
            for item in list_response.data["upcoming_interviews"]
        )

        detail_url = reverse("interview-detail", kwargs={"interview_id": interview_id})
        patch_response = api_client.patch(
            detail_url,
            {"outcome": "passed", "interviewer_notes": "Strong system design."},
            format="json",
        )
        assert patch_response.status_code == status.HTTP_200_OK
        assert patch_response.data["outcome"] == "passed"
        assert patch_response.data["interviewer_notes"] == "Strong system design."

        prep_url = reverse(
            "interview-interview-prep",
            kwargs={"interview_id": interview_id},
        )
        with patch.object(InterviewPrepAgent, "generate") as mock_generate:
            interview = Interview.objects.get(id=interview_id)
            plan = InterviewPlan.objects.create(
                user=user,
                opportunity=interview.opportunity,
                application=interview.application,
                interview=interview,
                prompt_name="interview_prep",
                prompt_version=1,
                model_name="local-fallback",
                content={"prep_roadmap": ["Review APIs"]},
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
                "reasoning_summary": "Prep linked to interview.",
            }
            prep_response = api_client.post(prep_url)

        assert prep_response.status_code == status.HTTP_200_OK
        assert prep_response.data["interview_plan"]["interview_id"] == interview_id
        mock_generate.assert_called_once()
        assert mock_generate.call_args.kwargs.get("interview") is not None

    def test_prep_plan_detail_still_works(self, api_client, user, workflow):
        job = Job.objects.create(
            source="test",
            title="Engineer",
            company="TestCo",
            dedupe_key="dedupe-test-interview",
        )
        opportunity = Opportunity.objects.create(
            user=user,
            job=job,
            workflow_execution=workflow,
            status=OpportunityStatus.APPLIED,
        )
        plan = InterviewPlan.objects.create(
            user=user,
            opportunity=opportunity,
            prompt_name="interview_prep",
            prompt_version=1,
            model_name="local-fallback",
            content={"likely_questions": ["Why this role?"]},
            markdown="# Plan",
        )
        api_client.force_authenticate(user=user)
        detail_url = reverse("interview-detail", kwargs={"interview_id": plan.id})
        response = api_client.get(detail_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "prep_plan"
        assert response.data["content"]["likely_questions"]

    def test_ownership_isolation(self, api_client, user):
        from apps.users.models import User

        other = User.objects.create_user(
            email="other-interview@example.com",
            password="pass12345",
        )
        interview = InterviewService().create_external(
            user,
            {"company": "PrivateCo", "job_title": "Role"},
        )
        api_client.force_authenticate(user=other)
        detail_url = reverse("interview-detail", kwargs={"interview_id": interview.id})
        assert api_client.get(detail_url).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAddInterviewChatClassification:
    def test_classify_add_interview_phrase(self):
        result = classify_follow_up(
            "Add interview for Staff Engineer at Acme on 2026-03-15"
        )
        assert result["intent"] == FOLLOW_UP_ADD_INTERVIEW
        assert result["params"]["company"] == "Acme"
        assert "Staff Engineer" in result["params"]["job_title"]

    def test_does_not_classify_prep_as_add(self):
        result = classify_follow_up("generate interview prep for active applications")
        assert result["intent"] != FOLLOW_UP_ADD_INTERVIEW
