from django.urls import path

from apps.jobs.views import (
    JobScheduleStatusView,
    OpportunityCoverLetterView,
    OpportunityDetailView,
    OpportunityEvaluateView,
    OpportunityInterviewPrepView,
    OpportunityListView,
    OpportunityMaterialsView,
    OpportunityResearchCompanyView,
    OpportunityTailorResumeView,
)

urlpatterns = [
    path("schedule-status/", JobScheduleStatusView.as_view(), name="job-schedule-status"),
    path("", OpportunityListView.as_view(), name="opportunity-list"),
    path("<uuid:opportunity_id>/", OpportunityDetailView.as_view(), name="opportunity-detail"),
    path(
        "<uuid:opportunity_id>/research-company/",
        OpportunityResearchCompanyView.as_view(),
        name="opportunity-research-company",
    ),
    path(
        "<uuid:opportunity_id>/evaluate/",
        OpportunityEvaluateView.as_view(),
        name="opportunity-evaluate",
    ),
    path(
        "<uuid:opportunity_id>/tailor-resume/",
        OpportunityTailorResumeView.as_view(),
        name="opportunity-tailor-resume",
    ),
    path(
        "<uuid:opportunity_id>/cover-letter/",
        OpportunityCoverLetterView.as_view(),
        name="opportunity-cover-letter",
    ),
    path(
        "<uuid:opportunity_id>/materials/",
        OpportunityMaterialsView.as_view(),
        name="opportunity-materials",
    ),
    path(
        "<uuid:opportunity_id>/interview-prep/",
        OpportunityInterviewPrepView.as_view(),
        name="opportunity-interview-prep",
    ),
]
