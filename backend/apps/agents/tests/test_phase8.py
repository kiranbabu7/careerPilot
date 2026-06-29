"""Phase 8 tests — agent run inspection, workflow timeline, and decisions."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.decision import DECISION_AGENT_NAME, DecisionAgent
from apps.agents.decision_provider import DecisionGenerationResult, DecisionProvider
from apps.agents.models import AgentExecution, AgentExecutionStatus, DecisionRecommendation
from apps.applications.models import Application, ApplicationStage
from apps.applications.repositories import ApplicationRepository
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.memory.models import ActivityEvent, MemoryEntry
from apps.resumes.tests.test_phase2 import user
from apps.users.models import User
from apps.workflows.models import WorkflowExecution
from apps.workflows.timeline import WorkflowTimelineService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other-phase8@example.com",
        password="pass12345",
        first_name="Other",
        last_name="User",
    )


@pytest.fixture
def workflow(user):
    return WorkflowExecution.objects.create(
        user=user,
        name="Phase 8 workflow",
        goal="Find staff engineer roles",
        status="completed",
        started_at=timezone.now() - timedelta(hours=1),
        completed_at=timezone.now(),
        result={"discovered_count": 3, "evaluated_count": 3, "top_match_score": 85},
    )


@pytest.fixture
def job():
    return Job.objects.create(
        external_id="ext-phase8",
        source="linkedin",
        title="Staff Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        description="Python Django leadership",
        dedupe_key="dedupe-acme-phase8",
    )


@pytest.fixture
def opportunity(user, workflow, job):
    return Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.SAVED,
        match_score=85,
        evaluation={"match_score": 85, "recommendation": "strong_match"},
    )


@pytest.fixture
def planner_execution(user, workflow):
    started = timezone.now() - timedelta(minutes=10)
    completed = timezone.now() - timedelta(minutes=9)
    return AgentExecution.objects.create(
        user=user,
        workflow_execution=workflow,
        agent_name="planner",
        status=AgentExecutionStatus.COMPLETED,
        input_data={"goal": workflow.goal},
        output_data={"suggested_steps": []},
        reasoning_summary="Planning complete.",
        started_at=started,
        completed_at=completed,
    )


@pytest.fixture
def failed_execution(user, workflow):
    started = timezone.now() - timedelta(minutes=5)
    completed = timezone.now() - timedelta(minutes=4)
    return AgentExecution.objects.create(
        user=user,
        workflow_execution=workflow,
        agent_name="job_search",
        status=AgentExecutionStatus.FAILED,
        input_data={"goal": workflow.goal},
        output_data={},
        error_message="Provider timeout",
        started_at=started,
        completed_at=completed,
    )


@pytest.mark.django_db
class TestAgentExecutionAPI:
    def test_list_executions_paginated(
        self, api_client, user, planner_execution, failed_execution
    ):
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("agent-execution-list"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2
        assert "agent_label" in data["results"][0]
        assert "duration_ms" in data["results"][0]
        assert "has_error" in data["results"][0]

    def test_filter_by_agent_name(self, api_client, user, planner_execution, failed_execution):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("agent-execution-list"),
            {"agent_name": "planner"},
        )
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["agent_name"] == "planner"

    def test_filter_by_status(self, api_client, user, planner_execution, failed_execution):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("agent-execution-list"),
            {"status": "failed"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 1
        assert response.json()["results"][0]["status"] == "failed"

    def test_execution_detail(self, api_client, user, planner_execution):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("agent-execution-detail", kwargs={"execution_id": planner_execution.id})
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(planner_execution.id)
        assert "input_data" in data
        assert "output_data" in data

    def test_execution_ownership_isolation(
        self, api_client, other_user, planner_execution
    ):
        api_client.force_authenticate(user=other_user)
        response = api_client.get(
            reverse("agent-execution-detail", kwargs={"execution_id": planner_execution.id})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestWorkflowTimeline:
    def test_timeline_ordering(self, user, workflow, planner_execution, failed_execution):
        items = WorkflowTimelineService().build_timeline(workflow)
        assert len(items) >= 3
        timestamps = [item["timestamp"] for item in items]
        assert timestamps == sorted(timestamps)

    def test_timeline_api(self, api_client, user, workflow, planner_execution):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("workflow-timeline", kwargs={"workflow_id": workflow.id})
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["workflow_id"] == str(workflow.id)
        assert any(item["item_type"] == "agent_completed" for item in data["items"])

    def test_timeline_ownership(self, api_client, other_user, workflow):
        api_client.force_authenticate(user=other_user)
        response = api_client.get(
            reverse("workflow-timeline", kwargs={"workflow_id": workflow.id})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_workflow_detail_still_returns_agent_executions(
        self, api_client, user, workflow, planner_execution
    ):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse("workflow-detail", kwargs={"workflow_id": workflow.id})
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["agent_executions"]) >= 1


@pytest.mark.django_db
class TestDecisionAgent:
    def _mock_provider(self):
        provider = DecisionProvider()
        provider.generate = lambda prompt_text, context: DecisionGenerationResult(
            summary="Prioritize interview prep.",
            rationale="You have an active application pipeline.",
            actions=[
                {
                    "action_type": "application",
                    "target_id": "app-1",
                    "title": "Follow up on application",
                    "reason": "Applied stage needs attention.",
                    "urgency": "high",
                    "route": "/applications",
                }
            ],
            model_name="test-model",
            used_fallback=False,
        )
        return provider

    def test_generate_decision_with_fallback_provider(self, user, opportunity):
        agent = DecisionAgent(provider=self._mock_provider())
        with patch.object(
            agent.prompt_service,
            "render",
            return_value={
                "name": "decision",
                "version": 1,
                "source": "filesystem",
                "rendered_text": "prompt",
            },
        ):
            result = agent.generate(user)

        recommendation = result["recommendation"]
        execution = result["execution"]
        assert recommendation.status == "completed"
        assert execution.agent_name == DECISION_AGENT_NAME
        assert len(recommendation.actions) == 1
        assert ActivityEvent.objects.filter(
            user=user,
            event_type=ActivityEvent.EventType.DECISION_GENERATED,
        ).exists()
        assert MemoryEntry.objects.filter(user=user, category="decision").exists()

    def test_deterministic_fallback_actions(self, user, opportunity):
        from apps.agents.decision_context import build_decision_context

        context = build_decision_context(user)
        result = DecisionProvider()._deterministic_fallback(context)
        assert result.used_fallback is True
        assert len(result.actions) >= 1

    def test_decision_generate_api(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        with patch.object(DecisionAgent, "generate") as mock_generate:
            recommendation = DecisionRecommendation.objects.create(
                user=user,
                status="completed",
                summary="Test summary",
                rationale="Test rationale",
                actions=[],
                model_name="test",
            )
            execution = AgentExecution.objects.create(
                user=user,
                agent_name=DECISION_AGENT_NAME,
                status=AgentExecutionStatus.COMPLETED,
            )
            recommendation.agent_execution = execution
            recommendation.save()
            mock_generate.return_value = {
                "recommendation": recommendation,
                "execution": execution,
                "reasoning_summary": "Done",
            }
            response = api_client.post(reverse("decision-list-create"), {}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "recommendation" in response.json()

    def test_decision_latest_and_history(self, api_client, user):
        DecisionRecommendation.objects.create(
            user=user,
            status="completed",
            summary="Older",
            actions=[],
        )
        latest = DecisionRecommendation.objects.create(
            user=user,
            status="completed",
            summary="Latest recommendation",
            actions=[{"action_type": "profile", "title": "Complete profile", "reason": "x", "urgency": "low", "route": "/"}],
        )
        api_client.force_authenticate(user=user)

        latest_response = api_client.get(reverse("decision-latest"))
        assert latest_response.status_code == status.HTTP_200_OK
        assert latest_response.json()["id"] == str(latest.id)

        list_response = api_client.get(reverse("decision-list-create"))
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.json()["count"] == 2

        detail_response = api_client.get(
            reverse("decision-detail", kwargs={"recommendation_id": latest.id})
        )
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.json()["summary"] == "Latest recommendation"

    def test_decision_ownership(self, api_client, other_user, user):
        recommendation = DecisionRecommendation.objects.create(
            user=user,
            status="completed",
            summary="Private",
            actions=[],
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.get(
            reverse("decision-detail", kwargs={"recommendation_id": recommendation.id})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPlannerAgentic:
    def test_planner_prompt_renders_from_filesystem(self):
        from apps.agents.planner_context import build_planner_prompt_variables
        from apps.prompts.services import PromptService

        variables = build_planner_prompt_variables(
            {
                "goal": "Find remote senior backend roles at growth-stage startups",
                "workflow_intent": "job_discovery",
                "preferences": {
                    "target_roles": ["Backend Engineer"],
                    "target_locations": ["Remote"],
                    "remote_preference": "remote",
                    "skills": ["Python"],
                    "career_goals": "Staff engineer path",
                },
                "active_resume": None,
                "memory_snippets": [],
                "pipeline_counts": {"applications": 0, "materials": 0, "interview_plans": 0},
            }
        )
        rendered = PromptService().render("planner", variables)
        assert rendered["name"] == "planner"
        assert "startup" in rendered["rendered_text"].lower()

    def test_planner_provider_parses_json(self):
        from apps.agents.planner_provider import PlannerProvider
        from apps.providers.llm.json_output import parse_json_content

        provider = PlannerProvider()
        parsed = parse_json_content(
            '{"intent":"job_discovery","constraints":{"role":"backend"},'
            '"tool_plan":[{"tool":"job_search","reason":"search","auto_run":true,"params":{}}],'
            '"success_criteria":["find roles"],"reasoning_summary":"ok",'
            '"user_visible_plan":"Search jobs.","requires_confirmation":false}'
        )
        context = {"goal": "Find backend roles", "workflow_intent": "job_discovery"}
        result = provider._normalize_plan(parsed, context, used_fallback=False)
        assert result.intent == "job_discovery"
        assert result.tool_plan[0]["tool"] == "job_search"
        assert result.requires_confirmation is False

    def test_planner_deterministic_extracts_startup_constraints(self):
        from apps.agents.planner_provider import extract_constraints_from_goal

        constraints = extract_constraints_from_goal(
            "Find remote senior backend roles at growth-stage startups"
        )
        assert constraints["requires_company_research"] is True
        assert constraints["company_stage"] == "growth-stage startup"


@pytest.mark.django_db
class TestPlannerDecisionStep:
    def test_review_decisions_step_when_pipeline_exists(self, user, opportunity):
        ApplicationRepository().create_from_opportunity(user, opportunity)
        from apps.agents.planner import PlannerAgent

        context = PlannerAgent().build_context(user, "Find roles")
        steps = PlannerAgent()._suggest_steps(context)
        keys = [step["key"] for step in steps]
        assert "review_decisions" in keys

    def test_no_review_decisions_without_pipeline(self, user):
        from apps.agents.planner import PlannerAgent

        context = PlannerAgent().build_context(user, "Find roles")
        steps = PlannerAgent()._suggest_steps(context)
        keys = [step["key"] for step in steps]
        assert "review_decisions" not in keys
