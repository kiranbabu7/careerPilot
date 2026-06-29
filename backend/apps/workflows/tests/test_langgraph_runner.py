"""Tests for LangGraph workflow orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from apps.agents.planner_provider import (
    build_default_tool_plan,
    extract_constraints_from_goal,
    tool_plan_to_planned_agents,
)
from apps.workflows.intent import (
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
)
from apps.resumes.tests.test_phase2 import user  # noqa: F401
from apps.workflows.langgraph_runner import LangGraphWorkflowRunner, build_workflow_graph
from apps.workflows.services import WorkflowService
from apps.workflows.tool_registry import ToolResult


def _build_mock_planner(goal, tool_plan, *, workflow_intent=None, replan_side_effect=None):
    resolved_intent = workflow_intent or WORKFLOW_INTENT_JOB_DISCOVERY
    mock_planner = MagicMock()
    mock_planner.plan.return_value = {
        "execution": MagicMock(id="planner-exec"),
        "plan_summary": "Planning complete.",
        "suggested_steps": [],
        "planned_agents": tool_plan_to_planned_agents(tool_plan, resolved_intent),
        "workflow_intent": resolved_intent,
        "context": {"goal": goal, "preferences": {}, "planner_constraints": {}},
        "constraints": extract_constraints_from_goal(goal),
        "tool_plan": tool_plan,
        "success_criteria": ["Discover roles"],
        "user_visible_plan": "Search then evaluate.",
        "requires_confirmation": False,
    }
    if replan_side_effect is not None:
        mock_planner.replan.side_effect = replan_side_effect
    else:
        mock_planner.replan.return_value = {
            "execution": MagicMock(),
            "action": "continue",
            "reason": "Proceed.",
            "tools_to_insert": [],
            "message": "",
        }
    return mock_planner


def _build_mock_registry(tool_results):
    mock_registry = MagicMock()
    mock_registry.execute.side_effect = tool_results
    mock_registry.get.return_value = MagicMock(
        auto_run=True, requires_confirmation=False
    )
    mock_registry.agent_name_for.side_effect = lambda key: key

    def _merge_result(workflow, tool_key, tool_result):
        workflow.result = {
            **(workflow.result or {}),
            **tool_result.data,
            "tool_results": [
                *list((workflow.result or {}).get("tool_results") or []),
                {"tool": tool_key, "summary": tool_result.summary},
            ],
        }
        workflow.save(update_fields=["result", "updated_at"])

    mock_registry.merge_result.side_effect = _merge_result
    return mock_registry


@pytest.mark.django_db
class TestLangGraphRunner:
    def test_langgraph_runs_job_discovery_tool_sequence(self, user):
        goal = "Find remote senior backend roles at growth-stage startups"
        tool_plan = build_default_tool_plan(
            WORKFLOW_INTENT_JOB_DISCOVERY,
            extract_constraints_from_goal(goal),
        )
        tool_results = [
            ToolResult(
                tool="job_search",
                success=True,
                summary="Found 2 roles.",
                data={
                    "discovered_count": 2,
                    "provider_summary": {"providers": {}},
                    "job_search_summary": "Found 2 roles.",
                },
                execution=MagicMock(id="search-exec"),
            ),
            ToolResult(
                tool="job_evaluation",
                success=True,
                summary="Evaluated 2 roles.",
                data={
                    "evaluated_count": 2,
                    "accepted_count": 1,
                    "borderline_count": 1,
                    "rejected_count": 0,
                    "top_match_score": 78,
                    "evaluation_executions": [],
                },
            ),
            ToolResult(
                tool="company_research",
                success=True,
                summary="Researched companies.",
                data={"companies_researched": 2},
            ),
            ToolResult(
                tool="job_evaluation",
                success=True,
                summary="Re-evaluated researched roles.",
                data={
                    "evaluated_count": 0,
                    "accepted_count": 1,
                    "borderline_count": 1,
                    "rejected_count": 0,
                    "top_match_score": 78,
                    "evaluation_executions": [],
                },
            ),
        ]
        service = WorkflowService(planner=_build_mock_planner(goal, tool_plan))
        service._tool_registry = _build_mock_registry(tool_results)

        workflow = service.repo.create(
            user=user,
            name="LangGraph discovery",
            goal=goal,
            status="running",
        )

        with patch.object(service, "_seed_welcome_chat_message"):
            result = service.execute_workflow(user, workflow, goal=goal)

        assert service._tool_registry.execute.call_count == 4
        called_tools = [
            call.args[2] for call in service._tool_registry.execute.call_args_list
        ]
        assert called_tools == [
            "job_search",
            "job_evaluation",
            "company_research",
            "job_evaluation",
        ]
        assert result["discovered_count"] == 2
        assert result["tool_plan"]
        assert result["replan_events"] is not None

    def test_langgraph_inserts_tools_after_replan(self, user):
        goal = "Find backend roles"
        tool_plan = [
            {
                "tool": "job_search",
                "reason": "Discover",
                "auto_run": True,
                "params": {},
            },
            {
                "tool": "job_evaluation",
                "reason": "Evaluate",
                "auto_run": True,
                "params": {},
            },
        ]
        replan_calls = {"count": 0}

        def _replan(*_args, **_kwargs):
            replan_calls["count"] += 1
            if replan_calls["count"] == 1:
                return {
                    "execution": MagicMock(),
                    "action": "insert_tools",
                    "reason": "Need company research.",
                    "tools_to_insert": [
                        {
                            "tool": "company_research",
                            "reason": "Research",
                            "auto_run": True,
                            "params": {},
                        }
                    ],
                    "message": "",
                }
            return {
                "execution": MagicMock(),
                "action": "continue",
                "reason": "Proceed.",
                "tools_to_insert": [],
                "message": "",
            }

        tool_results = [
            ToolResult(
                tool="job_search",
                success=True,
                summary="Found roles.",
                data={"discovered_count": 1, "provider_summary": {"providers": {}}},
            ),
            ToolResult(
                tool="job_evaluation",
                success=True,
                summary="Evaluated.",
                data={
                    "evaluated_count": 1,
                    "accepted_count": 1,
                    "borderline_count": 0,
                    "rejected_count": 0,
                    "top_match_score": 80,
                    "evaluation_executions": [],
                },
            ),
            ToolResult(
                tool="company_research",
                success=True,
                summary="Researched.",
                data={"companies_researched": 1},
            ),
        ]
        service = WorkflowService(
            planner=_build_mock_planner(goal, tool_plan, replan_side_effect=_replan)
        )
        service._tool_registry = _build_mock_registry(tool_results)
        workflow = service.repo.create(
            user=user, name="Insert tools", goal=goal, status="running"
        )

        with patch.object(service, "_seed_welcome_chat_message"):
            result = service.execute_workflow(user, workflow, goal=goal)

        called_tools = [
            call.args[2] for call in service._tool_registry.execute.call_args_list
        ]
        assert "company_research" in called_tools
        assert any(
            event.get("action") == "insert_tools"
            for event in result["replan_events"]
        )

    def test_langgraph_pauses_for_user_confirmation(self, user):
        goal = "Tailor my resume for a backend role"
        tool_plan = [
            {
                "tool": "ask_user",
                "reason": "User must select a role",
                "auto_run": False,
                "params": {"action": "tailor_resume"},
            }
        ]
        mock_registry = MagicMock()
        mock_registry.get.return_value = MagicMock(
            auto_run=False,
            requires_confirmation=True,
            description="Confirm tailoring.",
        )
        mock_registry.agent_name_for.return_value = "ask_user"
        mock_registry.merge_result.side_effect = lambda workflow, tool_key, tool_result: None

        service = WorkflowService(
            planner=_build_mock_planner(
                goal,
                tool_plan,
                workflow_intent=WORKFLOW_INTENT_TAILOR_RESUME,
            )
        )
        service._tool_registry = mock_registry
        workflow = service.repo.create(
            user=user, name="Pause test", goal=goal, status="running"
        )

        with patch.object(service, "_seed_welcome_chat_message"):
            with patch.object(service, "_build_tailor_options_payload", return_value=[]):
                result = LangGraphWorkflowRunner().run(service, user, workflow, goal)

        mock_registry.execute.assert_not_called()
        workflow.refresh_from_db()
        assert workflow.status == "completed"
        assert result["next_action"]

    def test_langgraph_marks_failure_on_fail_with_reason(self, user):
        goal = "Find backend roles"
        tool_plan = [
            {
                "tool": "job_search",
                "reason": "Discover",
                "auto_run": True,
                "params": {},
            }
        ]
        mock_planner = _build_mock_planner(goal, tool_plan)
        mock_planner.replan.return_value = {
            "execution": MagicMock(),
            "action": "fail_with_reason",
            "reason": "Provider outage",
            "message": "Job search provider unavailable.",
            "tools_to_insert": [],
        }
        tool_results = [
            ToolResult(
                tool="job_search",
                success=False,
                summary="Failed.",
                data={"discovered_count": 0, "provider_summary": {"providers": {}}},
            )
        ]
        service = WorkflowService(planner=mock_planner)
        service._tool_registry = _build_mock_registry(tool_results)
        workflow = service.repo.create(
            user=user, name="Fail test", goal=goal, status="running"
        )

        with pytest.raises(RuntimeError, match="provider unavailable"):
            LangGraphWorkflowRunner().run(service, user, workflow, goal)

        workflow.refresh_from_db()
        assert workflow.status == "failed"
        assert workflow.error_message

    def test_langgraph_preserves_workflow_result_contract(self, user):
        goal = "Find remote backend roles"
        tool_plan = build_default_tool_plan(WORKFLOW_INTENT_JOB_DISCOVERY, {})
        tool_results = [
            ToolResult(
                tool="job_search",
                success=True,
                summary="Found roles.",
                data={
                    "discovered_count": 1,
                    "provider_summary": {"providers": {"linkedin": 1}},
                    "job_search_summary": "Found roles.",
                },
                execution=MagicMock(id="search-exec"),
            ),
            ToolResult(
                tool="job_evaluation",
                success=True,
                summary="Evaluated.",
                data={
                    "evaluated_count": 1,
                    "accepted_count": 1,
                    "borderline_count": 0,
                    "rejected_count": 0,
                    "top_match_score": 85,
                    "evaluation_executions": [],
                },
            ),
        ]
        service = WorkflowService(planner=_build_mock_planner(goal, tool_plan))
        service._tool_registry = _build_mock_registry(tool_results)
        workflow = service.repo.create(
            user=user, name="Contract test", goal=goal, status="running"
        )

        with patch.object(service, "_seed_welcome_chat_message"):
            result = LangGraphWorkflowRunner().run(service, user, workflow, goal)

        for key in (
            "workflow",
            "planner_execution",
            "plan_summary",
            "workflow_intent",
            "planned_agents",
            "completed_agents",
            "discovered_count",
            "tool_plan",
            "plan_history",
            "replan_events",
            "next_action",
            "constraints",
        ):
            assert key in result

        workflow.refresh_from_db()
        assert workflow.result.get("tool_results") is not None
        assert workflow.result.get("completed_agents")


def test_build_workflow_graph_compiles():
    graph = build_workflow_graph()
    assert graph is not None
