"""Guided workflow LangGraph subgraph (tailor, cover letter, application tracking)."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from apps.workflows.langgraph_nodes import (
    complete_workflow_node,
    guided_finalize_node,
    pause_for_user_node,
    route_after_guided_tool_executor,
    tool_executor_node,
)
from apps.workflows.langgraph_state import WorkflowGraphState


def build_guided_graph():
    """Guided on-demand flows with optional user pause."""
    builder = StateGraph(WorkflowGraphState)
    builder.add_node("tool_executor", tool_executor_node)
    builder.add_node("guided_finalize", guided_finalize_node)
    builder.add_node("pause_for_user", pause_for_user_node)
    builder.add_node("complete", complete_workflow_node)

    builder.set_entry_point("tool_executor")
    builder.add_conditional_edges("tool_executor", route_after_guided_tool_executor)
    builder.add_edge("guided_finalize", "complete")
    builder.add_edge("pause_for_user", "complete")
    builder.add_edge("complete", END)

    return builder.compile()
