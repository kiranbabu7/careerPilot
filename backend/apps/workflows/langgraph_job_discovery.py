"""Job discovery LangGraph subgraph (tool loop with replan)."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from apps.workflows.langgraph_nodes import (
    complete_workflow_node,
    fail_workflow_node,
    pause_for_user_node,
    replan_node,
    route_after_replan,
    route_after_tool_executor,
    tool_executor_node,
)
from apps.workflows.langgraph_state import WorkflowGraphState


def build_job_discovery_graph():
    """Compile the job-discovery tool loop subgraph."""
    builder = StateGraph(WorkflowGraphState)
    builder.add_node("tool_executor", tool_executor_node)
    builder.add_node("replan", replan_node)
    builder.add_node("pause_for_user", pause_for_user_node)
    builder.add_node("complete", complete_workflow_node)
    builder.add_node("fail", fail_workflow_node)

    builder.set_entry_point("tool_executor")
    builder.add_conditional_edges("tool_executor", route_after_tool_executor)
    builder.add_conditional_edges("replan", route_after_replan)
    builder.add_edge("pause_for_user", "complete")
    builder.add_edge("complete", END)
    builder.add_edge("fail", END)

    return builder.compile()
