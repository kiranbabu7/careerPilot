from django.urls import path

from apps.workflows.views import (
    WorkflowActionView,
    WorkflowDetailView,
    WorkflowJobSearchView,
    WorkflowListCreateView,
    WorkflowMessagesView,
    WorkflowTailorOptionsView,
    WorkflowTailorResumeView,
    WorkflowTimelineView,
)

urlpatterns = [
    path("", WorkflowListCreateView.as_view(), name="workflow-list"),
    path(
        "<uuid:workflow_id>/",
        WorkflowDetailView.as_view(),
        name="workflow-detail",
    ),
    path(
        "<uuid:workflow_id>/timeline/",
        WorkflowTimelineView.as_view(),
        name="workflow-timeline",
    ),
    path(
        "<uuid:workflow_id>/job-search/",
        WorkflowJobSearchView.as_view(),
        name="workflow-job-search",
    ),
    path(
        "<uuid:workflow_id>/tailor-options/",
        WorkflowTailorOptionsView.as_view(),
        name="workflow-tailor-options",
    ),
    path(
        "<uuid:workflow_id>/tailor-resume/",
        WorkflowTailorResumeView.as_view(),
        name="workflow-tailor-resume",
    ),
    path(
        "<uuid:workflow_id>/messages/",
        WorkflowMessagesView.as_view(),
        name="workflow-messages",
    ),
    path(
        "<uuid:workflow_id>/actions/",
        WorkflowActionView.as_view(),
        name="workflow-actions",
    ),
]
