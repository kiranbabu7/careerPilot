from django.urls import path

from apps.applications.views import (
    ApplicationCreateFromOpportunityView,
    ApplicationDetailView,
    ApplicationForOpportunityView,
    ApplicationInterviewPrepView,
    ApplicationListView,
    InterviewDetailView,
    InterviewInterviewPrepView,
    InterviewListView,
)

urlpatterns = [
    path("", ApplicationListView.as_view(), name="application-list"),
    path(
        "for-opportunity/<uuid:opportunity_id>/",
        ApplicationForOpportunityView.as_view(),
        name="application-for-opportunity",
    ),
    path(
        "from-opportunity/<uuid:opportunity_id>/",
        ApplicationCreateFromOpportunityView.as_view(),
        name="application-create-from-opportunity",
    ),
    path(
        "<uuid:application_id>/",
        ApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "<uuid:application_id>/interview-prep/",
        ApplicationInterviewPrepView.as_view(),
        name="application-interview-prep",
    ),
]

interview_urlpatterns = [
    path("", InterviewListView.as_view(), name="interview-list"),
    path(
        "<uuid:interview_id>/",
        InterviewDetailView.as_view(),
        name="interview-detail",
    ),
    path(
        "<uuid:interview_id>/interview-prep/",
        InterviewInterviewPrepView.as_view(),
        name="interview-interview-prep",
    ),
]
