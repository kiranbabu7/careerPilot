"""Celery application for CareerPilot background work."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careerpilot.settings")

app = Celery("careerpilot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_configure.connect
def init_sentry_for_worker(**kwargs):
    """Ensure Celery workers pick up Sentry when Django settings load late."""
    from django.conf import settings

    if not getattr(settings, "SENTRY_DSN", ""):
        return

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    if sentry_sdk.get_client() is not None:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=getattr(settings, "SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1),
        send_default_pii=False,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(level=None, event_level="ERROR"),
        ],
    )
