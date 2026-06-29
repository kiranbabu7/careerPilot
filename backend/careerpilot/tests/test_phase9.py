"""Phase 9 production readiness tests."""

import json
import logging

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from careerpilot.logging_config import redact_sensitive_text
from careerpilot.production import INSECURE_SECRET_KEY, validate_production_settings


@pytest.fixture
def api_client():
    return APIClient()


class TestProductionValidation:
    def test_debug_mode_allows_insecure_secret(self):
        validate_production_settings(
            debug=True,
            secret_key=INSECURE_SECRET_KEY,
            allowed_hosts=["localhost"],
        )

    def test_production_rejects_insecure_secret(self):
        with pytest.raises(ValueError, match="DJANGO_SECRET_KEY"):
            validate_production_settings(
                debug=False,
                secret_key=INSECURE_SECRET_KEY,
                allowed_hosts=["example.com"],
            )

    def test_production_requires_allowed_hosts(self):
        with pytest.raises(ValueError, match="DJANGO_ALLOWED_HOSTS"):
            validate_production_settings(
                debug=False,
                secret_key="secure-production-key",
                allowed_hosts=[],
            )

    def test_production_requires_s3_bucket_when_enabled(self):
        with pytest.raises(ValueError, match="AWS_STORAGE_BUCKET_NAME"):
            validate_production_settings(
                debug=False,
                secret_key="secure-production-key",
                allowed_hosts=["example.com"],
                use_s3_storage=True,
                s3_bucket="",
            )


class TestMediaStorage:
    def test_local_storage_by_default(self, monkeypatch):
        monkeypatch.delenv("USE_S3_STORAGE", raising=False)
        monkeypatch.delenv("AWS_STORAGE_BUCKET_NAME", raising=False)
        from careerpilot.storage import build_default_storage, use_s3_storage

        assert use_s3_storage(debug=True) is False
        backend = build_default_storage(debug=True)
        assert backend["BACKEND"] == "django.core.files.storage.FileSystemStorage"

    def test_s3_when_bucket_configured(self, monkeypatch):
        monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "careerpilot-prod")
        monkeypatch.setenv("USE_S3_STORAGE", "true")
        from careerpilot.storage import build_default_storage, use_s3_storage

        assert use_s3_storage(debug=False) is True
        backend = build_default_storage(debug=False)
        assert backend["BACKEND"] == "storages.backends.s3.S3Storage"
        assert backend["OPTIONS"]["bucket_name"] == "careerpilot-prod"
        assert backend["OPTIONS"]["querystring_auth"] is True


class TestSensitiveLogging:
    def test_redacts_api_tokens(self):
        message = "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz123456"
        redacted = redact_sensitive_text(message)
        assert "sk-abc" not in redacted
        assert "***REDACTED***" in redacted


@pytest.mark.django_db
class TestHealthEndpoints:
    def test_liveness_always_ok(self, api_client):
        response = api_client.get(reverse("health-live"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"

    def test_readiness_checks_dependencies(self, api_client, monkeypatch):
        monkeypatch.setattr("careerpilot.views.check_database", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_redis", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_celery_broker", lambda: True)

        response = api_client.get(reverse("health-ready"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
        assert response.data["database"] == "connected"
        assert response.data["redis"] == "connected"
        assert response.data["celery_broker"] == "connected"

    def test_readiness_degraded_when_redis_unavailable(self, api_client, monkeypatch):
        monkeypatch.setattr("careerpilot.views.check_database", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_redis", lambda: False)
        monkeypatch.setattr("careerpilot.views.check_celery_broker", lambda: True)

        response = api_client.get(reverse("health-ready"))
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "degraded"
        assert response.data["redis"] == "unavailable"

    def test_health_alias_matches_readiness(self, api_client, monkeypatch):
        monkeypatch.setattr("careerpilot.views.check_database", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_redis", lambda: True)
        monkeypatch.setattr("careerpilot.views.check_celery_broker", lambda: True)

        response = api_client.get(reverse("health"))
        assert response.status_code == status.HTTP_200_OK
        assert "database" in response.data
        assert "redis" in response.data


class TestRequestIdMiddleware:
    def test_response_includes_request_id_header(self, api_client):
        response = api_client.get(
            reverse("health-live"),
            HTTP_X_REQUEST_ID="test-request-123",
        )
        assert response["X-Request-ID"] == "test-request-123"

    def test_generates_request_id_when_missing(self, api_client):
        response = api_client.get(reverse("health-live"))
        assert response["X-Request-ID"]
        assert len(response["X-Request-ID"]) >= 32


class TestStructuredLogging:
    def test_json_formatter_emits_parseable_payload(self):
        from careerpilot.logging_config import JsonLogFormatter

        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="apps.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="workflow completed",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-abc"
        payload = json.loads(formatter.format(record))
        assert payload["level"] == "INFO"
        assert payload["message"] == "workflow completed"
        assert payload["request_id"] == "req-abc"
