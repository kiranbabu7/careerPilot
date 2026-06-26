"""Versioned API routes."""

from django.urls import include, path

from careerpilot.views import HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/", include("apps.users.urls")),
    path("users/", include("apps.users.preference_urls")),
    path("resumes/", include("apps.resumes.urls")),
    path("dashboard/", include("apps.memory.urls")),
    path("workflows/", include("apps.workflows.urls")),
    path("opportunities/", include("apps.jobs.urls")),
    path("agents/", include("apps.agents.urls")),
]
