from django.urls import path

from apps.workflows.views import WorkflowJobSearchView, WorkflowListCreateView

urlpatterns = [
    path("", WorkflowListCreateView.as_view(), name="workflow-list"),
    path(
        "<uuid:workflow_id>/job-search/",
        WorkflowJobSearchView.as_view(),
        name="workflow-job-search",
    ),
]
