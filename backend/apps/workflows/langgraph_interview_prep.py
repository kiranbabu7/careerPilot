"""Interview prep LangGraph subgraph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from apps.workflows.langgraph_nodes import (
    complete_workflow_node,
    pause_for_user_node,
    route_after_simple_tool_executor,
    tool_executor_node,
)
from apps.workflows.langgraph_state import WorkflowGraphState


def build_interview_prep_graph():
    """Single-tool interview prep execution without replan."""
    builder = StateGraph(WorkflowGraphState)
    builder.add_node("tool_executor", tool_executor_node)
    builder.add_node("pause_for_user", pause_for_user_node)
    builder.add_node("complete", complete_workflow_node)

    builder.set_entry_point("tool_executor")
    builder.add_conditional_edges("tool_executor", route_after_simple_tool_executor)
    builder.add_edge("pause_for_user", "complete")
    builder.add_edge("complete", END)

    return builder.compile()
