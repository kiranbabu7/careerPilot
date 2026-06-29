"""LangGraph workflow state shape and merge helpers."""

from __future__ import annotations

import json
from typing import Any, TypedDict


class WorkflowGraphState(TypedDict, total=False):
  user_id: str
  workflow_id: str
  goal: str
  workflow_intent: str
  planned_agents: list[str]
  intent_classification: dict[str, Any]
  context: dict[str, Any]
  tool_queue: list[dict[str, Any]]
  current_step: dict[str, Any]
  last_tool_key: str
  last_tool_result: dict[str, Any]
  plan_history: list[dict[str, Any]]
  replan_events: list[dict[str, Any]]
  replan_action: str
  stopped_for_user: bool
  stop_message: str
  failed: bool
  error_message: str
  plan_result: dict[str, Any]
  rerun_mode: bool


def merge_state(current: WorkflowGraphState, update: WorkflowGraphState) -> WorkflowGraphState:
  """Shallow-merge graph state updates."""
  merged = dict(current)
  merged.update(update)
  return merged  # type: ignore[return-value]


def pop_next_tool(tool_queue: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
  """Pop the next tool step from the queue."""
  if not tool_queue:
    return None, []
  remaining = list(tool_queue)
  step = remaining.pop(0)
  return step, remaining


def safe_tool_result_payload(tool_key: str, tool_result) -> dict[str, Any]:
  """JSON-serializable tool result for replanner input."""
  serializable_data = {
    k: v
    for k, v in tool_result.data.items()
    if k not in ("evaluation_executions",)
  }
  return json.loads(
    json.dumps(
      {
        "tool": tool_key,
        "success": tool_result.success,
        "summary": tool_result.summary,
        "data": serializable_data,
      },
      default=str,
    )
  )
