"""Search rerun LangGraph subgraph (filtered pipeline tools only)."""

from __future__ import annotations

from django.utils import timezone

from langgraph.graph import END, StateGraph

from apps.workflows.langgraph_nodes import rerun_complete_node, rerun_tool_executor_node
from apps.workflows.langgraph_state import WorkflowGraphState
from apps.workflows.serializers import WorkflowExecutionSerializer


def rerun_init_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Initialize rerun state from pre-filtered tool queue in config."""
    cfg = config.get("configurable") or {}
    tool_queue = list(cfg.get("rerun_tool_queue") or state.get("tool_queue") or [])
    return {"tool_queue": tool_queue, "rerun_mode": True}


def build_rerun_graph():
    """Filtered job-search pipeline rerun without planner or replan."""
    builder = StateGraph(WorkflowGraphState)
    builder.add_node("rerun_init", rerun_init_node)
    builder.add_node("tool_executor", rerun_tool_executor_node)
    builder.add_node("complete", rerun_complete_node)

    builder.set_entry_point("rerun_init")
    builder.add_edge("rerun_init", "tool_executor")

    def _route_after_rerun_tool(state: WorkflowGraphState) -> str:
        if state.get("tool_queue"):
            return "tool_executor"
        return "complete"

    builder.add_conditional_edges("tool_executor", _route_after_rerun_tool)
    builder.add_edge("complete", END)

    return builder.compile()


class LangGraphRerunRunner:
    def __init__(self, graph=None):
        self.graph = graph or build_rerun_graph()

    def run(
        self,
        service,
        user,
        workflow,
        *,
        context: dict,
        tool_plan: list[dict],
        overrides: dict | None = None,
    ) -> dict:
        from apps.agents.serializers import AgentExecutionSerializer

        config = {
            "configurable": {
                "service": service,
                "user": user,
                "workflow": workflow,
                "context": context,
                "overrides": overrides or {},
                "rerun_tool_queue": tool_plan,
                "runtime": {
                    "job_search_execution": None,
                    "evaluation_executions": [],
                },
            }
        }

        initial_state: WorkflowGraphState = {
            "goal": workflow.goal or "",
            "workflow_intent": (workflow.result or {}).get("workflow_intent", "job_discovery"),
            "tool_queue": list(tool_plan),
            "rerun_mode": True,
        }

        self.graph.invoke(initial_state, config=config)

        workflow.refresh_from_db()
        result = workflow.result or {}
        runtime = config["configurable"]["runtime"]
        evaluation_executions = runtime.get("evaluation_executions") or []

        response = {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "discovered_count": result.get("discovered_count", 0),
            "provider_summary": result.get("provider_summary", {"providers": {}}),
            "job_search_summary": result.get("job_search_summary", ""),
            "evaluated_count": result.get("evaluated_count", 0),
            "accepted_count": result.get("accepted_count", 0),
            "borderline_count": result.get("borderline_count", 0),
            "rejected_count": result.get("rejected_count", 0),
            "top_match_score": result.get("top_match_score", 0),
            "evaluation_executions": evaluation_executions,
            "completed_agents": result.get("completed_agents", []),
        }
        job_search_execution = runtime.get("job_search_execution")
        if job_search_execution is not None:
            response["job_search_execution"] = AgentExecutionSerializer(
                job_search_execution
            ).data
        return response
