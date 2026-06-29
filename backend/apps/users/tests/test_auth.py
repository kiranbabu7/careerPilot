import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User, UserPreference
from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus
from apps.agents.models import AgentExecution, AgentExecutionStatus
from apps.prompts.models import PromptVersion


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


@pytest.mark.django_db
class TestHealthEndpoint:
    def test_health_returns_ok(self, api_client, monkeypatch):
        monkeypatch.setattr("careerpilot.views.check_database", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_redis", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_celery_broker", lambda: True)

        response = api_client.get(reverse("health"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
        assert response.data["database"] == "connected"
        assert response.data["redis"] == "connected"


@pytest.mark.django_db
class TestAuthEndpoints:
    def test_register_creates_user_and_returns_tokens(self, api_client):
        response = api_client.post(
            reverse("auth-register"),
            {
                "email": "new@example.com",
                "password": "securepass123",
                "first_name": "New",
                "last_name": "User",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == "new@example.com"
        assert User.objects.filter(email="new@example.com").exists()
        assert UserPreference.objects.filter(user__email="new@example.com").exists()

    def test_register_duplicate_email_fails(self, api_client, user):
        response = api_client.post(
            reverse("auth-register"),
            {"email": user.email, "password": "securepass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_returns_tokens(self, api_client, user):
        response = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "securepass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_login_invalid_credentials(self, api_client, user):
        response = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "wrongpassword"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_requires_auth(self, api_client):
        response = api_client.get(reverse("auth-me"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_returns_current_user(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("auth-me"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_refresh_token(self, api_client, user):
        login = api_client.post(
            reverse("auth-login"),
            {"email": user.email, "password": "securepass123"},
            format="json",
        )
        response = api_client.post(
            reverse("auth-refresh"),
            {"refresh": login.data["refresh"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data


@pytest.mark.django_db
class TestModels:
    def test_user_uuid_primary_key(self, user):
        assert user.id is not None
        assert str(user.id) != ""

    def test_user_preference_defaults(self, user):
        pref = user.preferences
        assert pref.target_roles == []
        assert pref.remote_preference == "flexible"

    def test_workflow_execution_defaults(self, user):
        wf = WorkflowExecution.objects.create(
            user=user,
            name="Job Search",
            goal="Find senior engineer roles",
        )
        assert wf.status == WorkflowExecutionStatus.PENDING
        assert wf.context == {}

    def test_agent_execution_defaults(self, user):
        agent = AgentExecution.objects.create(
            user=user,
            agent_name="planner",
        )
        assert agent.status == AgentExecutionStatus.PENDING

    def test_prompt_version_unique_name_version(self, db):
        PromptVersion.objects.create(name="resume_tailor", version=1, template="Hello {name}")
        with pytest.raises(Exception):
            PromptVersion.objects.create(name="resume_tailor", version=1, template="Duplicate")

    def test_soft_delete(self, user):
        user.soft_delete()
        assert user.is_deleted
        assert not User.objects.filter(id=user.id).exists()
        assert User.all_objects.filter(id=user.id).exists()


@pytest.mark.django_db
class TestGoogleOAuth:
    def test_google_auth_without_config_fails(self, api_client, settings):
        settings.GOOGLE_OAUTH_CLIENT_ID = ""
        response = api_client.post(
            reverse("auth-google"),
            {"id_token": "fake-token"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_google_auth_with_mocked_provider(self, api_client, monkeypatch):
        from apps.providers.oauth.google import GoogleUserInfo
        from apps.users.services import AuthService

        def mock_verify(self, token):
            return GoogleUserInfo(
                google_id="google-123",
                email="google@example.com",
                first_name="Google",
                last_name="User",
                avatar_url="https://example.com/avatar.png",
            )

        monkeypatch.setattr(
            "apps.providers.oauth.google.GoogleOAuthProvider.verify_id_token",
            mock_verify,
        )

        from django.conf import settings as django_settings

        django_settings.GOOGLE_OAUTH_CLIENT_ID = "test-client-id"

        response = api_client.post(
            reverse("auth-google"),
            {"id_token": "valid-mocked-token"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user"]["email"] == "google@example.com"
        assert User.objects.filter(google_id="google-123").exists()
