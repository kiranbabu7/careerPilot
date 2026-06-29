"""Shared project-level views."""

from __future__ import annotations

import logging

import redis
from celery import current_app
from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
    except Exception:
        logger.exception("Database health check failed")
        return False


def check_redis() -> bool:
    try:
        client = redis.from_url(
            settings.CELERY_BROKER_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:
        logger.exception("Redis health check failed")
        return False


def check_celery_broker() -> bool:
    try:
        conn = current_app.connection()
        conn.ensure_connection(max_retries=1, timeout=2)
        conn.release()
        return True
    except Exception:
        logger.exception("Celery broker health check failed")
        return False


def build_readiness_payload() -> tuple[dict, int]:
    database_ok = check_database()
    redis_ok = check_redis()
    celery_ok = check_celery_broker()
    checks = {
        "database": "connected" if database_ok else "unavailable",
        "redis": "connected" if redis_ok else "unavailable",
        "celery_broker": "connected" if celery_ok else "unavailable",
    }
    all_ok = database_ok and redis_ok and celery_ok
    payload = {
        "status": "ok" if all_ok else "degraded",
        **checks,
    }
    code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return payload, code


class LivenessView(APIView):
    """Process is running — no dependency checks."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class ReadinessView(APIView):
    """Dependency checks for traffic routing."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        payload, code = build_readiness_payload()
        return Response(payload, status=code)


class HealthView(ReadinessView):
    """Backward-compatible alias for readiness checks."""

    pass
