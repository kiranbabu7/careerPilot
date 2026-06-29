"""Tests for incremental tool progress streaming during workflow execution."""

from unittest.mock import patch

import pytest

from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.tests.test_phase2 import user  # noqa: F401
from apps.workflows.services import WorkflowService
from apps.workflows.tool_progress import (
    append_tool_progress_event,
    complete_tool_progress,
    start_tool_progress,
)
from apps.workflows.tool_registry import WorkflowToolRegistry


@pytest.mark.django_db
def test_evaluate_discovered_opportunities_streams_progress(user):
    service = WorkflowService()
    workflow = service.repo.create(
        user=user,
        name="Progress eval",
        goal="Find backend roles",
        status="running",
    )
    jobs = [
        Job.objects.create(
            external_id=f"progress-{index}",
            source="linkedin",
            title=f"Engineer {index}",
            company=f"Co {index}",
            location="Remote",
            description="Python backend work",
            dedupe_key=f"dedupe-progress-{index}",
        )
        for index in range(2)
    ]
    for job in jobs:
        Opportunity.objects.create(
            user=user,
            job=job,
            workflow_execution=workflow,
            status=OpportunityStatus.DISCOVERED,
        )

    summary = service._evaluate_discovered_opportunities(
        user,
        workflow,
        {"preferences": {}, "planner_constraints": {}},
    )

    assert summary["evaluated_count"] == 2
    assert len(summary["evaluation_executions"]) == 1
    workflow.refresh_from_db()
    progress = workflow.result["tool_progress"]
    assert progress["tool"] == "job_evaluation"
    assert progress["status"] == "completed"
    assert progress["current"] == 2
    assert progress["total"] == 2
    assert len(progress["recent_events"]) == 2
    assert progress["recent_events"][0]["kind"] == "job_evaluation"
    assert progress["recent_events"][0]["job_title"] == "Engineer 0"

    detail = service.build_detail_response(workflow)
    assert detail["tool_progress"]["tool"] == "job_evaluation"


@pytest.mark.django_db
def test_company_research_streams_progress(user):
    service = WorkflowService()
    workflow = service.repo.create(
        user=user,
        name="Progress research",
        goal="Find backend roles",
        status="running",
    )
    jobs = [
        Job.objects.create(
            external_id=f"research-{index}",
            source="linkedin",
            title=f"Backend {index}",
            company=f"ResearchCo {index}",
            location="Remote",
            description="Python",
            dedupe_key=f"dedupe-research-{index}",
        )
        for index in range(2)
    ]
    for index, job in enumerate(jobs):
        Opportunity.objects.create(
            user=user,
            job=job,
            workflow_execution=workflow,
            status=OpportunityStatus.DISCOVERED,
            match_score=70 + index,
        )

    mock_research = {
        "available": True,
        "summary": "Growth-stage fintech.",
        "snippets": [],
    }

    with patch(
        "apps.agents.company_research.TavilyCompanyResearchProvider.enrich_company",
        return_value=mock_research,
    ):
        registry = WorkflowToolRegistry(service)
        result = registry.execute(
            user,
            workflow,
            "company_research",
            {"preferences": {}},
        )

    assert result.success
    assert result.data["companies_researched"] == 2
    from apps.agents.models import AgentExecution

    assert (
        AgentExecution.objects.filter(agent_name="company_research").count() == 1
    )
    workflow.refresh_from_db()
    progress = workflow.result["tool_progress"]
    assert progress["tool"] == "company_research"
    assert progress["status"] == "completed"
    assert progress["current"] == 2
    assert progress["recent_events"][0]["company"] == "ResearchCo 0"
    assert progress["recent_events"][1]["available"] is True


@pytest.mark.django_db
def test_tool_progress_helpers_update_workflow_result(user):
    workflow = WorkflowService().repo.create(
        user=user,
        name="Helper test",
        goal="Test",
        status="running",
        result={},
    )

    start_tool_progress(workflow, tool="job_evaluation", total=3, current_label="First role")
    workflow.refresh_from_db()
    assert workflow.result["tool_progress"]["status"] == "running"
    assert workflow.result["tool_progress"]["current_label"] == "First role"

    append_tool_progress_event(
        workflow,
        {
            "kind": "job_evaluation",
            "job_title": "Backend Engineer",
            "company": "Acme",
            "match_score": 82,
            "recommendation": "strong_match",
        },
    )
    workflow.refresh_from_db()
    assert workflow.result["tool_progress"]["current"] == 1
    assert workflow.result["tool_progress"]["recent_events"][0]["match_score"] == 82

    complete_tool_progress(workflow, tool="job_evaluation")
    workflow.refresh_from_db()
    assert workflow.result["tool_progress"]["status"] == "completed"
    assert workflow.result["tool_progress"]["current_label"] == ""
