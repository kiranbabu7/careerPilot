"""Incremental tool progress stored on workflow.result for live UI polling."""

from __future__ import annotations

from django.utils import timezone

MAX_RECENT_EVENTS = 20


def _progress_snapshot(workflow) -> dict:
    result = workflow.result or {}
    progress = result.get("tool_progress")
    return dict(progress) if isinstance(progress, dict) else {}


def start_tool_progress(
    workflow,
    *,
    tool: str,
    total: int,
    current_label: str = "",
) -> None:
    workflow.refresh_from_db()
    result = dict(workflow.result or {})
    result["tool_progress"] = {
        "tool": tool,
        "status": "running",
        "current": 0,
        "total": max(total, 0),
        "current_label": current_label,
        "recent_events": [],
        "updated_at": timezone.now().isoformat(),
    }
    workflow.result = result
    workflow.save(update_fields=["result", "updated_at"])


def update_tool_progress_label(workflow, *, current_label: str) -> None:
    workflow.refresh_from_db()
    result = dict(workflow.result or {})
    progress = _progress_snapshot(workflow)
    if not progress or progress.get("status") != "running":
        return
    progress["current_label"] = current_label
    progress["updated_at"] = timezone.now().isoformat()
    result["tool_progress"] = progress
    workflow.result = result
    workflow.save(update_fields=["result", "updated_at"])


def append_tool_progress_event(workflow, event: dict) -> None:
    workflow.refresh_from_db()
    result = dict(workflow.result or {})
    progress = _progress_snapshot(workflow)
    if not progress:
        return

    recent_events = list(progress.get("recent_events") or [])
    stamped = {**event, "at": timezone.now().isoformat()}
    recent_events.append(stamped)
    progress["recent_events"] = recent_events[-MAX_RECENT_EVENTS:]
    progress["current"] = len(progress["recent_events"])
    progress["updated_at"] = stamped["at"]
    result["tool_progress"] = progress
    workflow.result = result
    workflow.save(update_fields=["result", "updated_at"])


def complete_tool_progress(workflow, *, tool: str) -> None:
    workflow.refresh_from_db()
    result = dict(workflow.result or {})
    progress = _progress_snapshot(workflow)
    if progress.get("tool") != tool:
        return
    progress["status"] = "completed"
    progress["current_label"] = ""
    progress["updated_at"] = timezone.now().isoformat()
    result["tool_progress"] = progress
    workflow.result = result
    workflow.save(update_fields=["result", "updated_at"])


def clear_tool_progress(workflow) -> None:
    workflow.refresh_from_db()
    result = dict(workflow.result or {})
    if "tool_progress" not in result:
        return
    result.pop("tool_progress", None)
    workflow.result = result
    workflow.save(update_fields=["result", "updated_at"])
