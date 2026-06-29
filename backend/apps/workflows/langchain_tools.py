"""LangChain StructuredTool wrappers around WorkflowToolRegistry handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from apps.workflows.tool_registry import ToolResult, WorkflowToolRegistry

if TYPE_CHECKING:
    from apps.workflows.services import WorkflowService

TOOL_KEYS = (
    "job_search",
    "job_evaluation",
    "company_research",
    "interview_prep",
    "resume_tailor",
    "cover_letter",
    "decision",
    "list_applications",
    "add_interview",
    "ask_user",
)


class WorkflowToolInput(BaseModel):
    tool_key: str = Field(description="Registry tool key")
    params: dict[str, Any] = Field(default_factory=dict)


def _tool_result_to_dict(tool_key: str, result: ToolResult) -> dict[str, Any]:
    return {
        "tool": tool_key,
        "success": result.success,
        "summary": result.summary,
        "requires_user": result.requires_user,
        "user_message": result.user_message,
        "data": {
            k: v for k, v in result.data.items() if k not in ("evaluation_executions",)
        },
    }


def build_langchain_tools(
    service: WorkflowService,
    user,
    workflow,
    context: dict,
) -> list[StructuredTool]:
    """Build LangChain tools that delegate to WorkflowToolRegistry."""
    registry = service._get_tool_registry()

    def _make_handler(tool_key: str):
        def _run(params: dict | None = None) -> dict:
            tool_result = registry.execute(
                user,
                workflow,
                tool_key,
                context,
                params=params or {},
            )
            registry.merge_result(workflow, tool_key, tool_result)
            return _tool_result_to_dict(tool_key, tool_result)

        return _run

    tools: list[StructuredTool] = []
    for tool_key in TOOL_KEYS:
        tool_def = registry.get(tool_key)
        if tool_def is None:
            continue
        tools.append(
            StructuredTool.from_function(
                func=_make_handler(tool_key),
                name=tool_key,
                description=tool_def.description,
            )
        )
    return tools


def invoke_workflow_tool(
    service: WorkflowService,
    user,
    workflow,
    tool_key: str,
    context: dict,
    *,
    params: dict | None = None,
) -> ToolResult:
    """Shared entry point for graph nodes and chat follow-up actions."""
    registry = service._get_tool_registry()
    tool_result = registry.execute(
        user, workflow, tool_key, context, params=params or {}
    )
    registry.merge_result(workflow, tool_key, tool_result)
    return tool_result
