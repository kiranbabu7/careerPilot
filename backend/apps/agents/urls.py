from django.urls import path

from apps.agents.decision_views import (
    DecisionDetailView,
    DecisionLatestView,
    DecisionListCreateView,
)
from apps.agents.views import AgentExecutionDetailView, AgentExecutionListView

urlpatterns = [
    path("executions/", AgentExecutionListView.as_view(), name="agent-execution-list"),
    path(
        "executions/<uuid:execution_id>/",
        AgentExecutionDetailView.as_view(),
        name="agent-execution-detail",
    ),
]

decision_urlpatterns = [
    path("", DecisionListCreateView.as_view(), name="decision-list-create"),
    path("latest/", DecisionLatestView.as_view(), name="decision-latest"),
    path(
        "<uuid:recommendation_id>/",
        DecisionDetailView.as_view(),
        name="decision-detail",
    ),
]
