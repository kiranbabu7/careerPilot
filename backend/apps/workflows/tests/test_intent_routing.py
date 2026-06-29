"""Tests for workflow intent classification and pipeline routing."""

from unittest.mock import MagicMock, patch

import pytest

from apps.agents.interview_prep import INTERVIEW_PREP_AGENT_NAME
from apps.applications.interview_provider import InterviewPlanGenerationResult
from apps.applications.models import ApplicationStage
from apps.applications.repositories import ApplicationRepository
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.tests.test_phase2 import user
from apps.jobs.tests.test_phase5 import preferences
from apps.workflows.intent import (
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_CONVERSATIONAL,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    INTERVIEW_PREP_SCOPE_APPLICATION,
    INTERVIEW_PREP_SCOPE_GENERAL,
    build_intent_classification,
    build_planned_agents,
    classify_conversational_variant,
    classify_interview_prep_scope,
    classify_workflow_intent,
    is_resume_based_interview_prep,
)
from apps.workflows.services import WorkflowService


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        (
            "Tailor my resume for staff engineer positions in fintech",
            WORKFLOW_INTENT_TAILOR_RESUME,
        ),
        ("Customize my resume for backend roles", WORKFLOW_INTENT_TAILOR_RESUME),
        ("Write a cover letter for Stripe", WORKFLOW_INTENT_COVER_LETTER),
        ("Interview prep for my Google onsite", WORKFLOW_INTENT_INTERVIEW_PREP),
        (
            "Prepare for system design interviews in the next two weeks",
            WORKFLOW_INTENT_INTERVIEW_PREP,
        ),
        ("Track my application pipeline", WORKFLOW_INTENT_APPLICATION_TRACKING),
        ("Find backend engineer jobs in NYC", WORKFLOW_INTENT_JOB_DISCOVERY),
        ("Search for remote Python roles", WORKFLOW_INTENT_JOB_DISCOVERY),
        ("Help me land a product manager role", WORKFLOW_INTENT_JOB_DISCOVERY),
        ("what can you do?", WORKFLOW_INTENT_CONVERSATIONAL),
        ("how does this work?", WORKFLOW_INTENT_CONVERSATIONAL),
        ("hello", WORKFLOW_INTENT_CONVERSATIONAL),
        ("what's 2+2?", WORKFLOW_INTENT_CONVERSATIONAL),
        ("thanks for the help", WORKFLOW_INTENT_CONVERSATIONAL),
    ],
)
def test_classify_workflow_intent(goal, expected):
    assert classify_workflow_intent(goal) == expected


@pytest.mark.parametrize(
    ("intent", "expected_agents"),
    [
        (WORKFLOW_INTENT_JOB_DISCOVERY, ["planner", "job_search", "job_evaluation"]),
        (WORKFLOW_INTENT_CONVERSATIONAL, ["planner"]),
        (WORKFLOW_INTENT_TAILOR_RESUME, ["planner"]),
        (WORKFLOW_INTENT_COVER_LETTER, ["planner"]),
        (WORKFLOW_INTENT_INTERVIEW_PREP, ["planner", "interview_prep"]),
        (WORKFLOW_INTENT_APPLICATION_TRACKING, ["planner"]),
    ],
)
def test_build_planned_agents(intent, expected_agents):
    assert build_planned_agents(intent) == expected_agents


def test_build_intent_classification_includes_matched_phrase():
    result = build_intent_classification("Tailor my resume for staff engineer roles")
    assert result["intent"] == WORKFLOW_INTENT_TAILOR_RESUME
    assert result["method"] == "rule_based"
    assert result["matched_phrase"] == "tailor my resume"
    assert result["planned_agents"] == ["planner"]


def test_build_intent_classification_defaults_for_generic_goal():
    result = build_intent_classification("Help me land a product manager role")
    assert result["intent"] == WORKFLOW_INTENT_JOB_DISCOVERY
    assert result["planned_agents"] == ["planner", "job_search", "job_evaluation"]
    assert result["matched_phrase"] is None


def test_build_intent_classification_marks_conversational_variant():
    result = build_intent_classification("what can you do?")
    assert result["intent"] == WORKFLOW_INTENT_CONVERSATIONAL
    assert result["planned_agents"] == ["planner"]
    assert result["conversational_variant"] == "help"
    assert result["matched_phrase"] == "what can you do"


@pytest.mark.parametrize(
    ("goal", "expected_variant"),
    [
        ("hello", "greeting"),
        ("what can you do?", "help"),
        ("what's 2+2?", "off_topic"),
    ],
)
def test_classify_conversational_variant(goal, expected_variant):
    assert classify_conversational_variant(goal) == expected_variant


@pytest.mark.django_db
def test_start_workflow_conversational_goal_skips_job_agents(user):
    service = WorkflowService()
    with patch("apps.workflows.services.dispatch_workflow") as mock_dispatch:
        result = service.start_workflow(user, goal="what can you do?")
        mock_dispatch.assert_called_once()

    workflow = service.get_execution(user, result["workflow"]["id"])
    assert workflow.result["intent_classification"]["intent"] == WORKFLOW_INTENT_CONVERSATIONAL
    assert workflow.result["workflow_intent"] == WORKFLOW_INTENT_CONVERSATIONAL
    assert workflow.result["planned_agents"] == ["planner"]
    assert "job_search" not in workflow.result["planned_agents"]


@pytest.mark.django_db
def test_start_workflow_persists_intent_classification(user):
    service = WorkflowService()
    with patch("apps.workflows.services.dispatch_workflow") as mock_dispatch:
        result = service.start_workflow(user, goal="Tailor my resume for fintech")
        mock_dispatch.assert_called_once()

    workflow = service.get_execution(user, result["workflow"]["id"])
    assert workflow.result["intent_classification"]["intent"] == WORKFLOW_INTENT_TAILOR_RESUME
    assert workflow.result["workflow_intent"] == WORKFLOW_INTENT_TAILOR_RESUME
    assert workflow.result["planned_agents"] == ["planner"]
    assert workflow.context["workflow_intent"] == WORKFLOW_INTENT_TAILOR_RESUME


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        (
            "Create a Interview Prep plan for 1 Week to revise everything mentioned in my resume",
            INTERVIEW_PREP_SCOPE_GENERAL,
        ),
        (
            "Prepare for system design interviews in the next two weeks",
            INTERVIEW_PREP_SCOPE_GENERAL,
        ),
        (
            "Interview prep for staff engineer onsite",
            INTERVIEW_PREP_SCOPE_GENERAL,
        ),
        (
            "Interview prep for my Google onsite",
            INTERVIEW_PREP_SCOPE_APPLICATION,
        ),
        (
            "Prepare for my interview at Stripe next week",
            INTERVIEW_PREP_SCOPE_APPLICATION,
        ),
    ],
)
def test_classify_interview_prep_scope(goal, expected):
    assert (
        classify_interview_prep_scope(
            goal,
            application_companies=("Google", "Athena Infonomics"),
            opportunity_companies=("Stripe",),
        )
        == expected
    )


def test_classify_interview_prep_scope_matches_pipeline_company():
    assert (
        classify_interview_prep_scope(
            "Interview prep for Athena Infonomics",
            application_companies=("Athena Infonomics",),
        )
        == INTERVIEW_PREP_SCOPE_APPLICATION
    )


def test_is_resume_based_interview_prep():
    assert is_resume_based_interview_prep(
        "revise everything mentioned in my resume over 1 week"
    )
    assert not is_resume_based_interview_prep("Interview prep for my Google onsite")


@pytest.mark.django_db
class TestWorkflowIntentRouting:
    def test_tailor_resume_skips_job_search(self, user):
        mock_job_search = MagicMock()
        mock_evaluation = MagicMock()
        service = WorkflowService(
            job_search_agent=mock_job_search,
            evaluation_agent=mock_evaluation,
        )
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for staff engineer positions in fintech",
            status="running",
        )

        result = service.execute_workflow(
            user,
            workflow,
            goal="Tailor my resume for staff engineer positions in fintech",
        )

        mock_job_search.search.assert_not_called()
        mock_evaluation.evaluate.assert_not_called()
        assert result["workflow_intent"] == WORKFLOW_INTENT_TAILOR_RESUME
        assert result["planned_agents"] == ["planner"]
        assert result["completed_agents"] == ["planner"]
        assert result["discovered_count"] == 0
        assert result["evaluated_count"] == 0
        assert result["next_action"]
        assert result.get("tailor_options") is not None
        assert result.get("tailor_selection_pending") is True

        workflow.refresh_from_db()
        assert workflow.status == "completed"
        assert workflow.result["workflow_intent"] == WORKFLOW_INTENT_TAILOR_RESUME

    def test_interview_prep_runs_interview_agent(self, user, preferences):
        from apps.agents.interview_prep import INTERVIEW_PREP_AGENT_NAME

        mock_job_search = MagicMock()
        mock_prep = MagicMock()
        mock_activity = MagicMock()
        mock_plan = MagicMock()
        mock_plan.id = "plan-1"
        mock_plan.opportunity.job.title = "Senior Software Engineer"
        mock_plan.opportunity.job.company = "General interview prep"
        mock_execution = MagicMock()
        mock_execution.id = "exec-prep-1"
        mock_prep.generate.return_value = {
            "execution": mock_execution,
            "plan": mock_plan,
            "reasoning_summary": "Prep generated.",
        }

        service = WorkflowService(
            job_search_agent=mock_job_search,
            interview_prep_agent=mock_prep,
            application_activity_service=mock_activity,
        )
        workflow = service.repo.create(
            user=user,
            name="System design prep",
            goal="Prepare for system design interviews in the next two weeks",
            status="running",
        )

        result = service.execute_workflow(
            user,
            workflow,
            goal="Prepare for system design interviews in the next two weeks",
        )

        mock_job_search.search.assert_not_called()
        mock_prep.generate.assert_called_once()
        mock_activity.record_interview_prep_generated.assert_called_once()
        assert result["workflow_intent"] == WORKFLOW_INTENT_INTERVIEW_PREP
        assert result["planned_agents"] == ["planner", "interview_prep"]
        assert INTERVIEW_PREP_AGENT_NAME in result["completed_agents"]
        assert result["interview_plan_id"] == "plan-1"
        assert "interview prep" in result["next_action"].lower()

        workflow.refresh_from_db()
        assert workflow.status == "completed"
        assert workflow.result["interview_plan_id"] == "plan-1"

    def test_interview_prep_skips_job_search(self, user):
        mock_job_search = MagicMock()
        mock_interview_prep = MagicMock()
        mock_activity = MagicMock()
        mock_plan = MagicMock()
        mock_plan.id = "plan-1"
        mock_plan.opportunity.job.title = "Staff Engineer"
        mock_plan.opportunity.job.company = "Acme"
        mock_execution = MagicMock()
        mock_execution.agent_name = INTERVIEW_PREP_AGENT_NAME
        mock_interview_prep.generate.return_value = {
            "plan": mock_plan,
            "execution": mock_execution,
            "reasoning_summary": "Prep plan created.",
        }

        service = WorkflowService(
            job_search_agent=mock_job_search,
            interview_prep_agent=mock_interview_prep,
            application_activity_service=mock_activity,
        )
        workflow = service.repo.create(
            user=user,
            name="Interview prep",
            goal="Interview prep for staff engineer onsite",
            status="running",
        )

        result = service.execute_workflow(
            user, workflow, goal="Interview prep for staff engineer onsite"
        )

        mock_job_search.search.assert_not_called()
        mock_interview_prep.generate.assert_called_once()
        assert result["workflow_intent"] == WORKFLOW_INTENT_INTERVIEW_PREP
        assert result["planned_agents"] == ["planner", "interview_prep"]
        assert result["completed_agents"] == ["planner", "interview_prep"]
        assert result["interview_plan_id"] == "plan-1"
        assert result["interview_prep_target_source"] == "general"

        workflow.refresh_from_db()
        assert workflow.status == "completed"
        assert workflow.result["interview_plan_id"] == "plan-1"

    def test_interview_prep_prefers_interviewing_application(
        self, user, preferences
    ):
        from apps.agents.interview_prep import InterviewPrepAgent
        from apps.applications.interview_provider import InterviewPrepProvider

        job = Job.objects.create(
            external_id="google-sde",
            source="linkedin",
            title="Staff Engineer",
            company="Google",
            location="Remote",
            is_remote=True,
            description="System design and distributed systems",
            dedupe_key="dedupe-google-sde",
        )
        opportunity = Opportunity.objects.create(
            user=user,
            job=job,
            status=OpportunityStatus.APPLIED,
            match_score=90,
            evaluation={"match_score": 90},
        )
        application, _ = ApplicationRepository().create_from_opportunity(
            user, opportunity
        )
        ApplicationRepository().update(
            application,
            stage=ApplicationStage.INTERVIEWING,
            stage_notes="Onsite scheduled",
        )

        provider = MagicMock(spec=InterviewPrepProvider)
        provider.generate.return_value = InterviewPlanGenerationResult(
            content={
                "prep_roadmap": ["Review system design"],
                "likely_questions": ["Design a URL shortener"],
                "system_design_topics": ["Caching"],
                "company_talking_points": ["Scale"],
                "resume_stories": ["Led migration"],
                "gaps_to_practice": ["Distributed tracing"],
                "day_by_day_checklist": [{"day": 1, "tasks": ["Read primer"]}],
            },
            markdown="# Interview Prep Plan",
            model_name="local-fallback",
            used_fallback=True,
        )

        service = WorkflowService(
            interview_prep_agent=InterviewPrepAgent(provider=provider),
        )
        workflow = service.repo.create(
            user=user,
            name="Google onsite prep",
            goal="Prepare for my Google onsite interview in the next two weeks",
            status="running",
        )

        result = service.execute_workflow(
            user,
            workflow,
            goal="Prepare for my Google onsite interview in the next two weeks",
        )

        assert result["workflow_intent"] == WORKFLOW_INTENT_INTERVIEW_PREP
        assert result["interview_prep_target_source"] == "application"
        assert result["selected_opportunity_id"] == str(opportunity.id)
        assert "interview_plan_id" in result
        provider.generate.assert_called_once()

    def test_interview_prep_resume_revision_skips_active_application(
        self, user, preferences
    ):
        from apps.agents.interview_prep import InterviewPrepAgent
        from apps.applications.interview_provider import InterviewPrepProvider

        job = Job.objects.create(
            external_id="athena-swe",
            source="linkedin",
            title="Senior Software Engineer",
            company="Athena Infonomics",
            location="Remote",
            is_remote=True,
            description="Data engineering platform",
            dedupe_key="dedupe-athena-swe",
        )
        opportunity = Opportunity.objects.create(
            user=user,
            job=job,
            status=OpportunityStatus.APPLIED,
            match_score=88,
            evaluation={"match_score": 88},
        )
        application, _ = ApplicationRepository().create_from_opportunity(
            user, opportunity
        )
        ApplicationRepository().update(
            application,
            stage=ApplicationStage.INTERVIEWING,
            stage_notes="Technical round",
        )

        provider = MagicMock(spec=InterviewPrepProvider)
        provider.generate.return_value = InterviewPlanGenerationResult(
            content={
                "prep_roadmap": ["Review resume projects"],
                "likely_questions": ["Tell me about a project"],
                "system_design_topics": [],
                "company_talking_points": [],
                "resume_stories": ["Led migration"],
                "gaps_to_practice": ["STAR stories"],
                "day_by_day_checklist": [{"day": 1, "tasks": ["Map resume bullets"]}],
            },
            markdown="# Resume Revision Prep",
            model_name="local-fallback",
            used_fallback=True,
        )

        service = WorkflowService(
            interview_prep_agent=InterviewPrepAgent(provider=provider),
        )
        goal = (
            "Create a Interview Prep plan for 1 Week to revise everything "
            "mentioned in my resume"
        )
        workflow = service.repo.create(
            user=user,
            name="Resume revision prep",
            goal=goal,
            status="running",
        )

        result = service.execute_workflow(user, workflow, goal=goal)

        assert result["workflow_intent"] == WORKFLOW_INTENT_INTERVIEW_PREP
        assert result["interview_prep_target_source"] == "general"
        assert result["selected_opportunity_id"] != str(opportunity.id)
        assert "resume" in result["next_action"].lower()
        provider.generate.assert_called_once()
        selected = service.opportunity_repo.get_for_user(
            user, result["selected_opportunity_id"]
        )
        assert selected is not None
        assert selected.job.company == "General interview prep"

    def test_interview_prep_general_goal_skips_application_without_company(
        self, user, preferences
    ):
        from apps.agents.interview_prep import InterviewPrepAgent
        from apps.applications.interview_provider import InterviewPrepProvider

        job = Job.objects.create(
            external_id="google-sde-2",
            source="linkedin",
            title="Staff Engineer",
            company="Google",
            location="Remote",
            is_remote=True,
            description="System design and distributed systems",
            dedupe_key="dedupe-google-sde-2",
        )
        opportunity = Opportunity.objects.create(
            user=user,
            job=job,
            status=OpportunityStatus.APPLIED,
            match_score=90,
            evaluation={"match_score": 90},
        )
        application, _ = ApplicationRepository().create_from_opportunity(
            user, opportunity
        )
        ApplicationRepository().update(
            application,
            stage=ApplicationStage.INTERVIEWING,
            stage_notes="Onsite scheduled",
        )

        provider = MagicMock(spec=InterviewPrepProvider)
        provider.generate.return_value = InterviewPlanGenerationResult(
            content={
                "prep_roadmap": ["Review system design"],
                "likely_questions": ["Design a URL shortener"],
                "system_design_topics": ["Caching"],
                "company_talking_points": [],
                "resume_stories": ["Led migration"],
                "gaps_to_practice": ["Distributed tracing"],
                "day_by_day_checklist": [{"day": 1, "tasks": ["Read primer"]}],
            },
            markdown="# Interview Prep Plan",
            model_name="local-fallback",
            used_fallback=True,
        )

        service = WorkflowService(
            interview_prep_agent=InterviewPrepAgent(provider=provider),
        )
        workflow = service.repo.create(
            user=user,
            name="System design prep",
            goal="Prepare for system design interviews in the next two weeks",
            status="running",
        )

        result = service.execute_workflow(
            user,
            workflow,
            goal="Prepare for system design interviews in the next two weeks",
        )

        assert result["workflow_intent"] == WORKFLOW_INTENT_INTERVIEW_PREP
        assert result["interview_prep_target_source"] == "general"
        assert result["selected_opportunity_id"] != str(opportunity.id)
        provider.generate.assert_called_once()

    def test_conversational_goal_skips_job_search(self, user):
        mock_job_search = MagicMock()
        mock_evaluation = MagicMock()
        service = WorkflowService(
            job_search_agent=mock_job_search,
            evaluation_agent=mock_evaluation,
        )
        workflow = service.repo.create(
            user=user,
            name="Capabilities",
            goal="what can you do?",
            status="running",
            result={
                "workflow_intent": WORKFLOW_INTENT_CONVERSATIONAL,
                "intent_classification": build_intent_classification("what can you do?"),
                "planned_agents": ["planner"],
                "completed_agents": [],
            },
            context={"workflow_intent": WORKFLOW_INTENT_CONVERSATIONAL},
        )

        with patch.object(service, "_seed_welcome_chat_message"):
            result = service.execute_workflow(user, workflow, goal="what can you do?")

        mock_job_search.search.assert_not_called()
        mock_evaluation.evaluate.assert_not_called()
        assert result["workflow_intent"] == WORKFLOW_INTENT_CONVERSATIONAL
        assert result["planned_agents"] == ["planner"]
        assert result["completed_agents"] == ["planner"]
        assert result["discovered_count"] == 0
        assert result["evaluated_count"] == 0
        assert "here's what i can help" in result["next_action"].lower()

        workflow.refresh_from_db()
        assert workflow.status == "completed"
        assert workflow.result["workflow_intent"] == WORKFLOW_INTENT_CONVERSATIONAL

    def test_job_discovery_still_runs_job_search(self, user, preferences):
        from apps.agents.job_search import JobSearchAgent
        from apps.jobs.services import JobSearchService
        from apps.providers.jobs.normalization import normalize_apify_item

        sample = {
            "id": "job-intent-1",
            "title": "Senior Backend Engineer",
            "companyName": "Acme Corp",
            "location": "Remote",
            "description": "Python Django PostgreSQL",
            "isRemote": True,
        }
        listing = normalize_apify_item(sample, source="linkedin")

        mock_apify = MagicMock()
        mock_apify.search_jobs.return_value = [listing]
        mock_apify.actor_ids = ["actor"]
        mock_apify.api_token = "token"
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = WorkflowService(
            job_search_agent=JobSearchAgent(
                search_service=JobSearchService(
                    apify_provider=mock_apify,
                    tavily_provider=mock_tavily,
                )
            ),
        )
        workflow = service.repo.create(
            user=user,
            name="Find backend roles",
            goal="Find backend engineer roles",
            status="running",
        )

        result = service.execute_workflow(user, workflow, goal="Find backend engineer roles")

        assert result["workflow_intent"] == WORKFLOW_INTENT_JOB_DISCOVERY
        assert result["planned_agents"] == ["planner", "job_search", "job_evaluation"]
        assert "planner" in result["completed_agents"]
        assert "job_search" in result["completed_agents"]
        assert result["discovered_count"] == 1
        assert result["evaluated_count"] == 1
        mock_apify.search_jobs.assert_called()

    def test_build_detail_response_includes_workflow_intent(self, user):
        service = WorkflowService()
        workflow = service.repo.create(
            user=user,
            name="Tailor resume",
            goal="Tailor my resume for fintech",
            status="completed",
            result={"workflow_intent": WORKFLOW_INTENT_TAILOR_RESUME, "next_action": "Pick one"},
        )

        detail = service.build_detail_response(workflow)

        assert detail["workflow_intent"] == WORKFLOW_INTENT_TAILOR_RESUME
        assert detail["planned_agents"] == ["planner"]
        assert detail["next_action"] == "Pick one"
