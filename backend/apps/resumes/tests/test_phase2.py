import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.memory.models import ActivityEvent, MemoryEntry
from apps.resumes.models import Resume, ResumeAnalysis
from apps.users.models import User, UserPreference


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        email="test@example.com",
        password="securepass123",
        first_name="Test",
        last_name="User",
    )
    UserPreference.objects.create(user=u)
    return u


def make_resume_file(
    content: str = "John Doe\nSoftware Engineer\nExperience: 5 years Python, Django, React",
    filename: str = "resume.txt",
    content_type: str = "text/plain",
) -> SimpleUploadedFile:
    return SimpleUploadedFile(filename, content.encode("utf-8"), content_type=content_type)


@pytest.mark.django_db
class TestPreferencesAPI:
    def test_get_preferences_requires_auth(self, api_client):
        response = api_client.get(reverse("user-preferences"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_preferences_returns_defaults(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("user-preferences"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["target_roles"] == []
        assert response.data["remote_preference"] == "flexible"

    def test_patch_preferences_updates_fields(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            reverse("user-preferences"),
            {
                "target_roles": ["Senior Engineer"],
                "target_locations": ["Remote"],
                "career_goals": "Land a staff role",
                "skills": ["Python", "Django"],
                "remote_preference": "remote",
                "salary_min": 120000,
                "salary_max": 180000,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["target_roles"] == ["Senior Engineer"]
        assert response.data["salary_min"] == 120000
        assert ActivityEvent.objects.filter(
            user=user,
            event_type=ActivityEvent.EventType.PREFERENCES_UPDATED,
        ).exists()
        assert MemoryEntry.objects.filter(user=user, category="preferences").exists()


@pytest.mark.django_db
class TestResumeAPI:
    def test_list_resumes_requires_auth(self, api_client):
        response = api_client.get(reverse("resume-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_upload_resume_txt(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file()},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["original_filename"] == "resume.txt"
        assert response.data["is_active"] is True
        assert response.data["latest_analysis"] is not None
        assert "health_score" in response.data["latest_analysis"]
        assert Resume.objects.filter(user=user).count() == 1
        assert ActivityEvent.objects.filter(user=user).count() >= 2

    def test_upload_invalid_extension(self, api_client, user):
        api_client.force_authenticate(user=user)
        bad_file = SimpleUploadedFile("resume.exe", b"binary", content_type="application/octet-stream")
        response = api_client.post(
            reverse("resume-list"),
            {"file": bad_file},
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_set_active_resume(self, api_client, user):
        api_client.force_authenticate(user=user)
        first = api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file(filename="first.txt")},
            format="multipart",
        )
        second = api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file(filename="second.txt")},
            format="multipart",
        )
        second_id = second.data["id"]
        response = api_client.post(reverse("resume-set-active", kwargs={"resume_id": second_id}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is True
        first_resume = Resume.objects.get(id=first.data["id"])
        assert first_resume.is_active is False

    def test_resume_detail(self, api_client, user):
        api_client.force_authenticate(user=user)
        upload = api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file()},
            format="multipart",
        )
        response = api_client.get(
            reverse("resume-detail", kwargs={"resume_id": upload.data["id"]}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["latest_analysis"] is not None


@pytest.mark.django_db
class TestResumeAnalysisFallback:
    def test_local_fallback_when_ai_not_configured(self, settings):
        settings.OPENAI_API_KEY = ""
        settings.OPENROUTER_BASE_URL = ""
        from apps.resumes.providers import ResumeAnalysisProvider

        result = ResumeAnalysisProvider().analyze(
            "John Doe\nSoftware Engineer\nSkills: Python, Django\nExperience: 5 years",
            {"target_roles": ["Staff Engineer"]},
        )
        assert result.used_fallback is True
        assert result.model_name == "local-fallback"
        assert 0 <= result.health_score <= 100
        assert len(result.strengths) >= 1

    def test_ai_provider_called_when_configured(self, settings, monkeypatch):
        settings.OPENAI_API_KEY = "test-key"
        settings.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        captured_payload = {}

        def mock_post(url, headers, json, timeout):
            captured_payload.update(json)
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"summary":"Strong engineer","health_score":85,'
                                        '"ats_score":78,"strengths":["Python"],'
                                        '"weaknesses":["Metrics"],"missing_keywords":["K8s"],'
                                        '"improvement_suggestions":["Add metrics"],'
                                        '"extracted_skills":["Python","Django"]}'
                                    )
                                }
                            }
                        ]
                    }

            return MockResponse()

        monkeypatch.setattr("apps.resumes.providers.requests.post", mock_post)
        from apps.resumes.providers import ResumeAnalysisProvider

        result = ResumeAnalysisProvider().analyze("Resume text with Python experience")
        assert result.used_fallback is False
        assert result.model_name == "google/gemini-2.5-flash"
        assert captured_payload["model"] == "google/gemini-2.5-flash"
        assert result.health_score == 85
        assert result.ats_score == 78


@pytest.mark.django_db
class TestDashboardAPI:
    def test_dashboard_requires_auth(self, api_client):
        response = api_client.get(reverse("dashboard-summary"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_summary_new_user(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("dashboard-summary"))
        assert response.status_code == status.HTTP_200_OK
        assert "profile_completion" in response.data
        assert response.data["active_resume"] is None
        assert "next_actions" in response.data
        assert len(response.data["next_actions"]) >= 1

    def test_dashboard_reflects_preferences_and_resume(self, api_client, user):
        api_client.force_authenticate(user=user)
        api_client.patch(
            reverse("user-preferences"),
            {"target_roles": ["Engineer"], "career_goals": "Grow"},
            format="json",
        )
        api_client.post(
            reverse("resume-list"),
            {"file": make_resume_file()},
            format="multipart",
        )
        response = api_client.get(reverse("dashboard-summary"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["profile_completion"] > 0
        assert response.data["active_resume"] is not None
        assert len(response.data["recent_activity"]) >= 1

    def test_dashboard_locations_requires_target_locations_or_remote_preference(
        self, api_client, user
    ):
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("dashboard-summary"))
        missing_keys = {item["key"] for item in response.data["completion_signals"]["missing"]}
        assert "locations" in missing_keys

        api_client.patch(
            reverse("user-preferences"),
            {"remote_preference": "remote"},
            format="json",
        )
        response = api_client.get(reverse("dashboard-summary"))
        missing_keys = {item["key"] for item in response.data["completion_signals"]["missing"]}
        assert "locations" not in missing_keys

        api_client.patch(
            reverse("user-preferences"),
            {
                "remote_preference": "remote",
                "target_locations": ["Hyderabad", "Bangalore"],
            },
            format="json",
        )
        response = api_client.get(reverse("dashboard-summary"))
        completed_keys = {
            item["key"] for item in response.data["completion_signals"]["completed"]
        }
        assert "locations" in completed_keys
        assert response.data["preferences_summary"]["target_locations"] == [
            "Hyderabad",
            "Bangalore",
        ]

    def test_dashboard_salary_stays_missing_until_set(self, api_client, user):
        api_client.force_authenticate(user=user)
        api_client.patch(
            reverse("user-preferences"),
            {
                "target_roles": ["Engineer"],
                "career_goals": "Grow",
                "remote_preference": "remote",
                "target_locations": ["Hyderabad", "Bangalore"],
                "skills": ["Python"],
            },
            format="json",
        )
        response = api_client.get(reverse("dashboard-summary"))
        missing_keys = {item["key"] for item in response.data["completion_signals"]["missing"]}
        assert "salary" in missing_keys
        assert response.data["profile_completion"] == 60


@pytest.mark.django_db
class TestExtraction:
    def test_extract_txt(self):
        from apps.resumes.extraction import extract_text

        file_obj = io.BytesIO(b"Hello resume content")
        text = extract_text(file_obj, "resume.txt")
        assert "Hello resume content" in text

    def test_validate_rejects_large_file(self, settings):
        from apps.resumes.extraction import ExtractionError, validate_resume_file

        with pytest.raises(ExtractionError, match="exceeds"):
            validate_resume_file("resume.txt", "text/plain", 10 * 1024 * 1024, 5 * 1024 * 1024)
