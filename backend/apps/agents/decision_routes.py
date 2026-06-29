"""Resolve decision action routes to valid frontend paths."""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

STATIC_ROUTES = {
    "/",
    "/opportunities",
    "/applications",
    "/interviews",
    "/resume",
    "/agent-runs",
    "/workspace",
    "/decisions",
    "/companies",
    "/settings",
}


def _looks_like_uuid(value: str) -> bool:
    return bool(value and UUID_PATTERN.match(value))


def _workspace_goal_url(goal: str) -> str:
    return f"/workspace?goal={quote(goal)}"


def _tailor_goal_from_title(title: str) -> str:
    normalized = title.strip()
    lowered = normalized.lower()
    for prefix in (
        "generate tailored resume for ",
        "tailor resume for ",
        "generate tailored resume ",
    ):
        if lowered.startswith(prefix):
            remainder = normalized[len(prefix) :].strip()
            if remainder:
                return f"Tailor my resume for {remainder}"
    if "cover letter" in lowered:
        for prefix in ("generate cover letter for ", "write cover letter for "):
            if lowered.startswith(prefix):
                remainder = normalized[len(prefix) :].strip()
                if remainder:
                    return f"Write a cover letter for {remainder}"
        return normalized or "Write a cover letter"
    if "tailor" in lowered and "resume" in lowered:
        return normalized if lowered.startswith("tailor") else f"Tailor my resume — {normalized}"
    return normalized or "Tailor my resume"


def _is_material_action(action_type: str, title: str) -> bool:
    if action_type == "material":
        return True
    lowered = title.lower()
    return ("tailor" in lowered and "resume" in lowered) or "cover letter" in lowered


def resolve_decision_action_route(
    action: dict,
    *,
    workflow_id: str | None = None,
) -> str:
    action_type = str(action.get("action_type", "profile"))
    target_id = str(action.get("target_id", "")).strip()
    title = str(action.get("title", "")).strip()
    raw_route = str(action.get("route", "/")).strip() or "/"

    if not raw_route.startswith("/"):
        raw_route = f"/{raw_route}"

    parsed = urlparse(raw_route)
    path = parsed.path.rstrip("/") or "/"
    query = parsed.query

    path_parts = [part for part in path.split("/") if part]
    embedded_id = ""
    if len(path_parts) >= 2 and _looks_like_uuid(path_parts[-1]):
        embedded_id = path_parts[-1]

    effective_id = target_id or embedded_id

    if _is_material_action(action_type, title):
        return _workspace_goal_url(_tailor_goal_from_title(title))

    if action_type == "opportunity" and effective_id:
        return f"/opportunities?selected={effective_id}"

    if action_type == "application":
        return "/applications"

    if action_type == "interview" and effective_id:
        return f"/interviews?selected={effective_id}&type=prep_plan"

    workflow_target = effective_id or (workflow_id or "")
    if action_type == "workflow" and workflow_target:
        return f"/workspace?workflow={workflow_target}"

    if action_type == "agent_run":
        return "/agent-runs"

    if action_type == "profile":
        return "/settings"

    if path in STATIC_ROUTES and not embedded_id:
        return f"{path}?{query}" if query else path

    if path_parts and path_parts[0] == "opportunities" and embedded_id:
        return f"/opportunities?selected={embedded_id}"

    if path_parts and path_parts[0] in {"workspace", "workflows"} and embedded_id:
        return f"/workspace?workflow={embedded_id}"

    if query and path in STATIC_ROUTES:
        return f"{path}?{query}"

    return "/"
