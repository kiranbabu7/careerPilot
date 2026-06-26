from django.urls import path

from apps.agents.views import AgentExecutionListView

urlpatterns = [
    path("executions/", AgentExecutionListView.as_view(), name="agent-execution-list"),
]
