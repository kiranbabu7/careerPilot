"""Tests for agent-driven resume tailoring workflow flow."""

from unittest.mock import MagicMock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.materials_provider import MaterialGenerationResult
from apps.resumes.models import Resume
from apps.resumes.tests.test_phase2 import user
from apps.users.models import UserPreference
from apps.workflows.intent import WORKFLOW_INTENT_TAILOR_RESUME
from apps.workflows.services import WorkflowService
from apps.workflows.tailor_options import build_tailor_options


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def preferences(user):
    pref, _ = UserPreference.objects.get_or_create(user=user)
    pref.target_roles = ["Staff Engineer"]
    pref.target_locations = ["Remote"]
    pref.remote_preference = "remote"
    pref.skills = ["Python", "Fintech", "AWS"]
    pref.career_goals = "Staff engineer in fintech"
    pref.save()
    return pref


@pytest.fixture
def active_resume(user):
    return Resume.objects.create(
        user=user,
        file=SimpleUploadedFile("resume.txt", b"Jane Doe\nStaff Engineer"),
        original_filename="resume.txt",
        content_type="text/plain",
        file_size=32,
        extracted_text="Jane Doe\nStaff Engineer with fintech and Python experience.",
        is_active=True,
    )


@pytest.fixture
def fintech_job():
    return Job.objects.create(
        external_id="fintech-staff-1",
        source="linkedin",
        title="Staff Engineer - Payments",
        company="FinCo",
        location="Remote",
        is_remote=True,
        description="Staff engineer role in fintech payments platform Python AWS",
        dedupe_key="dedupe-fintech-staff-1",
    )


@pytest.fixture
def other_job():
    return Job.objects.create(
        external_id="retail-eng-1",
        source="linkedin",
        title="Senior Retail Engineer",
        company="ShopCo",
        location="NYC",
        is_remote=False,
        description="Retail e-commerce platform",
        dedupe_key="dedupe-retail-eng-1",
    )


@pytest.fixture
def fintech_opportunity(user, fintech_job):
    return Opportunity.objects.create(
        user=user,
        job=fintech_job,
        status=OpportunityStatus.SAVED,
        match_score=88,
        evaluation={"match_score": 88, "recommendation": "strong_match"},
    )


@pytest.fixture
def rejected_opportunity(user, other_job):
    return Opportunity.objects.create(
        user=user,
        job=other_job,
        status=OpportunityStatus.REJECTED,
        match_score=42,
        evaluation={"match_score": 42, "recommendation": "weak_match"},
    )


@pytest.fixture
def mock_material_provider():
    provider = MagicMock()
    provider.generate.return_value = MaterialGenerationResult(
        content="# Jane Doe\n\n## Summary\nStaff engineer tailored resume.",
        model_name="test-model",
        used_fallback=False,
    )
    return provider


@pytest.mark.django_db
class TestTailorOptions:
    def test_build_tailor_options_ranks_by_goal_keywords(
        self, user, fintech_opportunity, rejected_opportunity
    ):
        opportunities = [rejected_opportunity, fintech_opportunity]
        options = build_tailor_options(
            opportunities,
            "Tailor my resume for staff engineer positions in fintech",
        )

        assert options["supports_custom_jd"] is True
        assert len(options["opportunities"]) >= 1
        assert options["opportunities"][0]["title"] == "Staff Engineer - Payments"
        assert options["opportunities"][0]["company"] == "FinCo"

    def test_tailor_workflow_returns_options_after_planner(
        self, user, preferences, fintech_opportunity
    ):
        service = WorkflowService()
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="running",
        )

        result = service.execute_workflow(
            user,
            workflow,
            goal="Tailor my resume for staff engineer positions in fintech",
        )

        assert result["workflow_intent"] == WORKFLOW_INTENT_TAILOR_RESUME
        assert result["tailor_options"]["supports_custom_jd"] is True
        assert result["tailor_selection_pending"] is True
        assert len(result["tailor_options"]["opportunities"]) >= 1
        assert "Select" in result["next_action"]

        workflow.refresh_from_db()
        assert workflow.result["tailor_options"]["opportunities"]

    def test_get_tailor_options_api(
        self, api_client, user, preferences, fintech_opportunity
    ):
        service = WorkflowService()
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="completed",
            result={
                "workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME,
                "tailor_selection_pending": True,
            },
        )
        api_client.force_authenticate(user=user)
        url = reverse("workflow-tailor-options", args=[workflow.id])

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tailor_options"]["supports_custom_jd"] is True
        assert len(response.data["tailor_options"]["opportunities"]) >= 1


@pytest.mark.django_db
class TestWorkflowTailorResume:
    def test_tailor_from_opportunity_id(
        self,
        user,
        preferences,
        active_resume,
        fintech_opportunity,
        mock_material_provider,
    ):
        from apps.agents.resume_tailoring import ResumeTailorAgent

        service = WorkflowService(
            resume_tailor_agent=ResumeTailorAgent(provider=mock_material_provider)
        )
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="completed",
            result={
                "workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME,
                "planned_agents": ["planner"],
                "completed_agents": ["planner"],
                "tailor_selection_pending": True,
            },
        )

        result = service.tailor_resume(
            user,
            workflow.id,
            opportunity_id=fintech_opportunity.id,
        )

        assert result is not None
        assert result["material"]["material_type"] == "tailored_resume"
        assert result["completed_agents"] == ["planner", "resume_tailor"]

        workflow.refresh_from_db()
        assert workflow.result["tailor_selection_pending"] is False
        assert workflow.result["tailored_material_id"]
        assert workflow.result["selected_opportunity_id"] == str(fintech_opportunity.id)

    def test_tailor_from_custom_job_description(
        self,
        user,
        preferences,
        active_resume,
        mock_material_provider,
    ):
        from apps.agents.resume_tailoring import ResumeTailorAgent

        service = WorkflowService(
            resume_tailor_agent=ResumeTailorAgent(provider=mock_material_provider)
        )
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="completed",
            result={
                "workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME,
                "planned_agents": ["planner"],
                "completed_agents": ["planner"],
                "tailor_selection_pending": True,
            },
        )

        result = service.tailor_resume(
            user,
            workflow.id,
            title="Staff Engineer",
            company="Stealth Fintech",
            job_description="Looking for a staff engineer with Python and payments experience.",
        )

        assert result is not None
        assert result["material"]["material_type"] == "tailored_resume"
        assert result["opportunity_id"]

        workflow.refresh_from_db()
        assert workflow.result["selected_target"]["custom_jd"] is True
        assert workflow.result["tailor_selection_pending"] is False

    def test_tailor_resume_api_from_opportunity(
        self,
        api_client,
        user,
        preferences,
        active_resume,
        fintech_opportunity,
        mock_material_provider,
    ):
        from apps.agents.resume_tailoring import ResumeTailorAgent

        service = WorkflowService(
            resume_tailor_agent=ResumeTailorAgent(provider=mock_material_provider)
        )
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="completed",
            result={
                "workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME,
                "planned_agents": ["planner"],
                "completed_agents": ["planner"],
                "tailor_selection_pending": True,
            },
        )
        api_client.force_authenticate(user=user)
        url = reverse("workflow-tailor-resume", args=[workflow.id])

        response = api_client.post(
            url,
            {"opportunity_id": str(fintech_opportunity.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["material"]["material_type"] == "tailored_resume"
        assert "resume_tailor" in response.data["completed_agents"]

    def test_tailor_resume_api_custom_jd(
        self,
        api_client,
        user,
        preferences,
        active_resume,
        mock_material_provider,
    ):
        from apps.agents.resume_tailoring import ResumeTailorAgent

        service = WorkflowService(
            resume_tailor_agent=ResumeTailorAgent(provider=mock_material_provider)
        )
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="completed",
            result={
                "workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME,
                "planned_agents": ["planner"],
                "completed_agents": ["planner"],
                "tailor_selection_pending": True,
            },
        )
        api_client.force_authenticate(user=user)
        url = reverse("workflow-tailor-resume", args=[workflow.id])

        response = api_client.post(
            url,
            {
                "title": "Staff Engineer",
                "company": "Stealth Fintech",
                "job_description": "Staff engineer with Python and payments platform experience.",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["material"]["material_type"] == "tailored_resume"

    def test_build_detail_includes_tailor_options(
        self, user, fintech_opportunity
    ):
        service = WorkflowService()
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for fintech",
            status="completed",
            result={
                "workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME,
                "tailor_options": {"opportunities": [], "supports_custom_jd": True},
                "tailor_selection_pending": True,
            },
        )

        detail = service.build_detail_response(workflow)

        assert detail["tailor_options"]["supports_custom_jd"] is True
        assert detail["tailor_selection_pending"] is True
