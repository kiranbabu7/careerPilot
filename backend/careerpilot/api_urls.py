"""Versioned API routes."""

from django.urls import include, path

from apps.agents.urls import decision_urlpatterns
from apps.applications.urls import interview_urlpatterns
from careerpilot.views import HealthView, LivenessView, ReadinessView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("health/live/", LivenessView.as_view(), name="health-live"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    path("auth/", include("apps.users.urls")),
    path("users/", include("apps.users.preference_urls")),
    path("resumes/", include("apps.resumes.urls")),
    path("dashboard/", include("apps.memory.urls")),
    path("workflows/", include("apps.workflows.urls")),
    path("opportunities/", include("apps.jobs.urls")),
    path("companies/", include("apps.jobs.company_urls")),
    path("applications/", include("apps.applications.urls")),
    path("interviews/", include(interview_urlpatterns)),
    path("agents/", include("apps.agents.urls")),
    path("decisions/", include(decision_urlpatterns)),
]
