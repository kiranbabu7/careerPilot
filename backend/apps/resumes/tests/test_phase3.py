import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.models import AgentExecution
from apps.memory.models import ActivityEvent, MemoryEntry
from apps.resumes.tests.test_phase2 import make_resume_file, user
from apps.users.models import UserPreference
from apps.users.profile_enrichment import ProfileEnrichmentService
from apps.workflows.models import WorkflowExecution


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestProfileEnrichment:
    def test_enriches_sparse_profile_from_analysis(self, user):
        from apps.resumes.models import Resume, ResumeAnalysis

        resume = Resume.objects.create(
            user=user,
            original_filename="resume.txt",
            content_type="text/plain",
            file_size=100,
            extracted_text="Senior Software Engineer with Python and Django experience.",
            is_active=True,
        )
        analysis = ResumeAnalysis.objects.create(
            resume=resume,
            model_name="test",
            raw_summary="Experienced backend engineer.",
            health_score=80,
            ats_score=75,
            extracted_skills=["Python", "Django", "PostgreSQL"],
        )

        result = ProfileEnrichmentService().enrich_from_resume(user, resume, analysis)
        assert result["enriched"] is True
        assert "skills" in result["fields_updated"]
        assert "target_roles" in result["fields_updated"]
        assert "career_goals" in result["fields_updated"]

        preference = UserPreference.objects.get(user=user)
        assert len(preference.skills) >= 3
        assert len(preference.target_roles) >= 1
        assert preference.career_goals

    def test_does_not_overwrite_explicit_preferences(self, user):
        from apps.resumes.models import Resume, ResumeAnalysis

        preference = UserPreference.objects.get(user=user)
        preference.target_roles = ["Staff Engineer"]
        preference.career_goals = "My explicit goal"
        preference.skills = ["Rust", "Go", "C++"]
        preference.save()

        resume = Resume.objects.create(
            user=user,
            original_filename="resume.txt",
            content_type="text/plain",
            file_size=100,
            extracted_text="Python developer",
            is_active=True,
        )
        analysis = ResumeAnalysis.objects.create(
            resume=resume,
            model_name="test",
            extracted_skills=["Python", "Django"],
        )

        result = ProfileEnrichmentService().enrich_from_resume(user, resume, analysis)
        assert result["enriched"] is False

        preference.refresh_from_db()
        assert preference.target_roles == ["Staff Engineer"]
        assert preference.career_goals == "My explicit goal"
        assert preference.skills == ["Rust", "Go", "C++"]


@pytest.mark.django_db
class TestResumeProfileEnrichmentIntegration:
    def test_upload_enriches_profile_and_records_events(self, api_client, user, monkeypatch):
        from apps.resumes.providers import AnalysisResult

        def mock_analyze(self, resume_text, preferences=None):
            return AnalysisResult(
                model_name="test-model",
                raw_summary="Strong Python engineer with Django experience.",
                health_score=85,
                ats_score=80,
                strengths=["Python"],
                weaknesses=[],
                missing_keywords=[],
                improvement_suggestions=[],
                extracted_skills=["Python", "Django", "React"],
            )

        monkeypatch.setattr(
            "apps.resumes.providers.ResumeAnalysisProvider.analyze",
            mock_analyze,
        )

        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file("Senior Software Engineer\nPython Django React")},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED

        preference = UserPreference.objects.get(user=user)
        assert len(preference.skills) >= 3
        assert preference.target_roles
        assert preference.career_goals

        assert ActivityEvent.objects.filter(
            user=user,
            event_type=ActivityEvent.EventType.PROFILE_ENRICHED,
        ).exists()
        assert MemoryEntry.objects.filter(user=user, category="profile_enrichment").exists()


@pytest.mark.django_db
class TestDashboardProfileCompletion:
    def test_upload_only_user_gains_meaningful_completion(self, api_client, user, monkeypatch):
        from apps.resumes.providers import AnalysisResult

        def mock_analyze(self, resume_text, preferences=None):
            return AnalysisResult(
                model_name="test-model",
                raw_summary="Backend engineer.",
                health_score=85,
                ats_score=80,
                strengths=[],
                weaknesses=[],
                missing_keywords=[],
                improvement_suggestions=[],
                extracted_skills=["Python", "Django", "PostgreSQL"],
            )

        monkeypatch.setattr(
            "apps.resumes.providers.ResumeAnalysisProvider.analyze",
            mock_analyze,
        )

        api_client.force_authenticate(user=user)
        api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file("Senior Software Engineer\nPython Django")},
            format="multipart",
        )

        response = api_client.get(reverse("dashboard-summary"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["profile_completion"] >= 65
        assert "completion_signals" in response.data
        missing_keys = {item["key"] for item in response.data["completion_signals"]["missing"]}
        assert "target_roles" not in missing_keys
        assert "skills" not in missing_keys
        assert "career_goals" not in missing_keys

        next_keys = {action["key"] for action in response.data["next_actions"]}
        assert "set_target_roles" not in next_keys
        assert "set_career_goals" not in next_keys


@pytest.mark.django_db
class TestWorkflowAPI:
    def test_start_workflow_requires_auth(self, api_client):
        response = api_client.post(
            reverse("workflow-list"),
            {"goal": "Find remote backend roles"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_start_workflow_creates_execution(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse("workflow-list"),
            {"goal": "Find remote senior backend roles at startups"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "workflow" in response.data
        assert "planner_execution" in response.data
        assert response.data["planner_execution"]["agent_name"] == "planner"
        assert response.data["plan_summary"]

        assert WorkflowExecution.objects.filter(user=user).count() == 1
        assert AgentExecution.objects.filter(user=user, agent_name="planner").count() == 1
        assert ActivityEvent.objects.filter(
            user=user,
            event_type=ActivityEvent.EventType.WORKFLOW_STARTED,
        ).exists()

    def test_start_workflow_rejects_empty_goal(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse("workflow-list"),
            {"goal": "  "},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
