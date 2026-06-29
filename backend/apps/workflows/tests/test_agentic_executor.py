"""Tests for the agentic workflow executor and tool registry."""

from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.agents.planner_provider import (
    PlannerProvider,
    build_default_tool_plan,
    extract_constraints_from_goal,
    tool_plan_to_planned_agents,
)
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.workflows.intent import WORKFLOW_INTENT_JOB_DISCOVERY
from apps.resumes.tests.test_phase2 import user  # noqa: F401
from apps.workflows.services import WorkflowService
from apps.agents.company_research import CompanyResearchAgent
from apps.workflows.tool_registry import ToolResult, WorkflowToolRegistry


def test_extract_constraints_growth_stage_startup_goal():
    goal = "Find remote senior backend roles at growth-stage startups"
    constraints = extract_constraints_from_goal(goal)
    assert constraints.get("location") == "remote"
    assert constraints.get("remote_preference") == "remote"
    assert constraints.get("seniority") == "senior"
    assert "backend" in constraints.get("role", "")
    assert constraints.get("company_stage") == "growth-stage startup"
    assert constraints.get("requires_company_research") is True


def test_default_tool_plan_evaluates_before_company_research():
    constraints = {"requires_company_research": True}
    plan = build_default_tool_plan(WORKFLOW_INTENT_JOB_DISCOVERY, constraints)
    tools = [step["tool"] for step in plan]
    assert tools == [
        "job_search",
        "job_evaluation",
        "company_research",
        "job_evaluation",
    ]


def test_default_tool_plan_without_company_research():
    plan = build_default_tool_plan(WORKFLOW_INTENT_JOB_DISCOVERY, {})
    tools = [step["tool"] for step in plan]
    assert tools == ["job_search", "job_evaluation"]


def test_tool_plan_to_planned_agents():
    plan = build_default_tool_plan(
        WORKFLOW_INTENT_JOB_DISCOVERY,
        {"requires_company_research": True},
    )
    agents = tool_plan_to_planned_agents(plan, WORKFLOW_INTENT_JOB_DISCOVERY)
    assert agents == [
        "planner",
        "job_search",
        "job_evaluation",
        "company_research",
    ]


def test_planner_provider_deterministic_fallback():
    context = {
        "goal": "Find remote senior backend roles at growth-stage startups",
        "workflow_intent": WORKFLOW_INTENT_JOB_DISCOVERY,
        "preferences": {},
    }
    result = PlannerProvider()._deterministic_plan(context)
    assert result.used_fallback is True
    assert result.constraints.get("requires_company_research") is True
    assert any(step["tool"] == "company_research" for step in result.tool_plan)


def test_replan_inserts_company_research_after_initial_evaluation():
    provider = PlannerProvider()
    replan = provider._deterministic_replan(
        {
            "last_tool_key": "job_evaluation",
            "workflow_result": {
                "discovered_count": 2,
                "constraints": {"requires_company_research": True},
                "completed_agents": ["planner", "job_search", "job_evaluation"],
            },
            "pending_tools": [],
        }
    )
    assert replan.action == "insert_tools"
    inserted_tools = [step["tool"] for step in replan.tools_to_insert]
    assert inserted_tools == ["company_research", "job_evaluation"]


def test_replan_does_not_insert_company_research_before_evaluation():
    provider = PlannerProvider()
    replan = provider._deterministic_replan(
        {
            "last_tool_key": "job_search",
            "workflow_result": {
                "discovered_count": 2,
                "constraints": {"requires_company_research": True},
                "completed_agents": ["planner", "job_search"],
            },
            "pending_tools": [{"tool": "job_evaluation"}],
        }
    )
    assert replan.action == "continue"


def test_replan_asks_user_after_empty_search_and_broaden():
    provider = PlannerProvider()
    replan = provider._deterministic_replan(
        {
            "last_tool_key": "job_search",
            "workflow_result": {
                "discovered_count": 0,
                "search_broadened": True,
                "constraints": {},
                "completed_agents": ["planner", "job_search"],
            },
            "pending_tools": [{"tool": "job_evaluation"}],
        }
    )
    assert replan.action == "continue"
    assert "evaluation" in replan.reason.lower()


def test_replan_asks_user_after_empty_search_when_no_pending_evaluation():
    provider = PlannerProvider()
    replan = provider._deterministic_replan(
        {
            "last_tool_key": "job_search",
            "workflow_result": {
                "discovered_count": 0,
                "search_broadened": True,
                "constraints": {},
                "completed_agents": ["planner", "job_search"],
            },
            "pending_tools": [],
        }
    )
    assert replan.action == "ask_user"


@pytest.mark.django_db
class TestAgenticExecutor:
    def test_execute_workflow_runs_tools_from_planner_plan(self, user):
        mock_registry = MagicMock()
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

        mock_planner = MagicMock()
        goal = "Find remote senior backend roles at growth-stage startups"
        tool_plan = build_default_tool_plan(
            WORKFLOW_INTENT_JOB_DISCOVERY,
            extract_constraints_from_goal(goal),
        )
        mock_planner.plan.return_value = {
            "execution": MagicMock(id="planner-exec"),
            "plan_summary": "Planning complete.",
            "suggested_steps": [],
            "planned_agents": tool_plan_to_planned_agents(
                tool_plan, WORKFLOW_INTENT_JOB_DISCOVERY
            ),
            "workflow_intent": WORKFLOW_INTENT_JOB_DISCOVERY,
            "context": {"goal": goal, "preferences": {}, "planner_constraints": {}},
            "constraints": extract_constraints_from_goal(goal),
            "tool_plan": tool_plan,
            "success_criteria": ["Discover roles", "Verify startup stage", "Evaluate"],
            "user_visible_plan": "Search, verify startups, then score matches.",
            "requires_confirmation": False,
        }
        mock_planner.replan.return_value = {
            "execution": MagicMock(),
            "action": "continue",
            "reason": "Proceed.",
            "tools_to_insert": [],
            "message": "",
        }

        service = WorkflowService(planner=mock_planner)
        service._tool_registry = mock_registry

        workflow = service.repo.create(
            user=user,
            name="Agentic discovery",
            goal=goal,
            status="running",
        )

        with patch.object(service, "_seed_welcome_chat_message"):
            result = service.execute_workflow(user, workflow, goal=goal)

        assert mock_registry.execute.call_count == 4
        called_tools = [call.args[2] for call in mock_registry.execute.call_args_list]
        assert called_tools == [
            "job_search",
            "job_evaluation",
            "company_research",
            "job_evaluation",
        ]
        assert result["discovered_count"] == 2
        assert result["evaluated_count"] == 0
        assert result["constraints"].get("requires_company_research") is True
        assert len(result["tool_plan"]) == 4

        workflow.refresh_from_db()
        assert workflow.result.get("replan_events") is not None
        assert workflow.result.get("plan_history")


@pytest.mark.django_db
def test_build_detail_response_hydrates_counts_from_opportunities(user):
    from apps.jobs.models import Job, Opportunity, OpportunityStatus

    service = WorkflowService()
    workflow = service.repo.create(
        user=user,
        name="Stale counts",
        goal="Find backend roles",
        status="completed",
        result={
            "workflow_intent": WORKFLOW_INTENT_JOB_DISCOVERY,
            "discovered_count": 0,
            "evaluated_count": 0,
            "accepted_count": 0,
        },
    )
    job = Job.objects.create(
        external_id="hydrate-1",
        source="linkedin",
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        description="Python",
        dedupe_key="hydrate-dedupe-1",
    )
    Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.DISCOVERED,
        match_score=82,
    )

    detail = service.build_detail_response(workflow)
    assert detail["discovered_count"] == 1
    assert detail["evaluated_count"] == 1
    assert detail["accepted_count"] == 1


@pytest.mark.django_db
def test_rerun_sets_running_and_resets_pipeline_agents(user):
    service = WorkflowService()
    workflow = service.repo.create(
        user=user,
        name="Rerun test",
        goal="Find remote senior backend roles at growth-stage startups",
        status="completed",
        completed_at=timezone.now(),
        result={
            "workflow_intent": WORKFLOW_INTENT_JOB_DISCOVERY,
            "completed_agents": ["planner", "job_search", "company_research", "job_evaluation"],
            "discovered_count": 2,
        },
    )

    with patch("apps.workflows.services.dispatch_rerun_job_search") as mock_dispatch:
        payload = service.rerun_job_search(user, workflow.id)

    assert mock_dispatch.called
    assert payload["status"] == "running"
    workflow.refresh_from_db()
    assert workflow.status == "running"
    assert workflow.completed_at is None
    assert "job_search" not in workflow.result["completed_agents"]
    assert "planner" in workflow.result["completed_agents"]


@pytest.mark.django_db
def test_build_detail_response_exposes_agentic_fields(user):
    service = WorkflowService()
    workflow = service.repo.create(
        user=user,
        name="Detail test",
        goal="Find roles",
        status="completed",
        result={
            "workflow_intent": WORKFLOW_INTENT_JOB_DISCOVERY,
            "planned_agents": ["planner", "job_search", "job_evaluation"],
            "completed_agents": ["planner", "job_search"],
            "tool_plan": [{"tool": "job_search", "reason": "Discover"}],
            "constraints": {"location": "remote"},
            "success_criteria": ["Find roles"],
            "user_visible_plan": "Search then evaluate.",
            "plan_history": [{"phase": "initial"}],
            "replan_events": [{"action": "continue"}],
        },
    )
    detail = service.build_detail_response(workflow)
    assert detail["constraints"] == {"location": "remote"}
    assert detail["tool_plan"][0]["tool"] == "job_search"
    assert detail["success_criteria"] == ["Find roles"]
    assert detail["user_visible_plan"] == "Search then evaluate."
    assert detail["plan_history"]
    assert detail["replan_events"]


@pytest.mark.django_db
def test_job_evaluation_handles_dict_snippets_with_company_stage(user):
    """Regression: agentic job_evaluation must not join dict snippet payloads."""
    goal = "Find remote senior backend roles at growth-stage startups"
    constraints = extract_constraints_from_goal(goal)
    service = WorkflowService()
    workflow = service.repo.create(
        user=user,
        name="Eval regression",
        goal=goal,
        status="running",
        result={
            "workflow_intent": WORKFLOW_INTENT_JOB_DISCOVERY,
            "constraints": constraints,
            "planner_constraints": constraints,
        },
    )
    job = Job.objects.create(
        external_id="eval-regression-1",
        source="linkedin",
        title="Senior Backend Engineer",
        company="GrowthCo",
        location="Remote",
        is_remote=True,
        description="Python Django PostgreSQL AWS",
        dedupe_key="dedupe-eval-regression-1",
        company_research={
            "available": True,
            "summary": "Growth-stage startup building payments infrastructure.",
            "snippets": [
                {
                    "title": "Series B",
                    "url": "https://example.com/series-b",
                    "snippet": "Venture-backed startup closed Series B funding.",
                    "category": "funding",
                }
            ],
        },
    )
    Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.DISCOVERED,
    )

    context = {
        "goal": goal,
        "preferences": {},
        "planner_constraints": constraints,
    }
    summary = service._evaluate_discovered_opportunities(user, workflow, context)

    assert summary["evaluated_count"] == 1
    assert summary["top_match_score"] > 0


@pytest.mark.django_db
class TestCompanyResearchGating:
    def test_skips_poor_matches_and_researches_viable(self, user):
        from unittest.mock import patch

        service = WorkflowService()
        workflow = service.repo.create(
            user=user,
            name="Gating test",
            goal="Find backend roles",
            status="running",
        )
        poor_job = Job.objects.create(
            external_id="poor-1",
            source="linkedin",
            title="Junior QA",
            company="LowFit Inc",
            location="On-site",
            description="Manual testing",
            dedupe_key="dedupe-poor-1",
        )
        viable_job = Job.objects.create(
            external_id="viable-1",
            source="linkedin",
            title="Senior Backend Engineer",
            company="GoodFit Inc",
            location="Remote",
            description="Python Django",
            dedupe_key="dedupe-viable-1",
        )
        poor_opp = Opportunity.objects.create(
            user=user,
            job=poor_job,
            workflow_execution=workflow,
            status=OpportunityStatus.REJECTED,
            match_score=30,
        )
        viable_opp = Opportunity.objects.create(
            user=user,
            job=viable_job,
            workflow_execution=workflow,
            status=OpportunityStatus.DISCOVERED,
            match_score=72,
        )
        unevaluated_opp = Opportunity.objects.create(
            user=user,
            job=Job.objects.create(
                external_id="uneval-1",
                source="linkedin",
                title="Staff Engineer",
                company="Pending Inc",
                location="Remote",
                description="Go",
                dedupe_key="dedupe-uneval-1",
            ),
            workflow_execution=workflow,
            status=OpportunityStatus.DISCOVERED,
            match_score=None,
        )

        registry = WorkflowToolRegistry(service)
        with patch.object(CompanyResearchAgent, "research_batch") as mock_research_batch:
            mock_execution = MagicMock()
            mock_research_batch.return_value = {
                "execution": mock_execution,
                "researched_count": 1,
                "available_count": 1,
                "results": [
                    {
                        "opportunity_id": str(viable_opp.id),
                        "company_research": {"available": True},
                    }
                ],
            }
            result = registry.execute(
                user,
                workflow,
                "company_research",
                {"goal": "Find backend roles", "preferences": {}},
            )

        researched_ids = {
            str(opportunity.id)
            for opportunity in mock_research_batch.call_args.args[1]
        }
        assert str(viable_opp.id) in researched_ids
        assert str(poor_opp.id) not in researched_ids
        assert str(unevaluated_opp.id) not in researched_ids
        assert result.data["companies_researched"] == 1
        assert "passed the match threshold" in result.summary
