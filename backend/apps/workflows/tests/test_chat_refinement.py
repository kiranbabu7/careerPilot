"""Tests for workflow chat refinement loop."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.applications.models import ApplicationStage
from apps.applications.repositories import ApplicationRepository
from apps.resumes.tests.test_phase2 import user
from apps.workflows.follow_up import (
    FOLLOW_UP_ADD_INTERVIEW,
    FOLLOW_UP_HELP,
    FOLLOW_UP_INTERVIEW_PREP,
    FOLLOW_UP_LIST_APPLICATIONS,
    FOLLOW_UP_QUESTION,
    FOLLOW_UP_RERUN_SEARCH,
    FOLLOW_UP_RESEARCH_COMPANY,
    FOLLOW_UP_SHOW_REJECTED,
    FOLLOW_UP_TAILOR_RESUME,
    FOLLOW_UP_COVER_LETTER,
    FOLLOW_UP_VIEW_INTERVIEW_PREP,
    FOLLOW_UP_VIEW_TAILORED_RESUME,
    FOLLOW_UP_DOWNLOAD_TAILORED_RESUME,
    FOLLOW_UP_VIEW_COVER_LETTER,
    FOLLOW_UP_DOWNLOAD_COVER_LETTER,
    build_contextual_actions,
    build_cover_letter_follow_up_actions,
    build_tailored_resume_follow_up_actions,
    build_view_cover_letter_action,
    build_view_interview_prep_action,
    build_view_tailored_resume_action,
    classify_follow_up,
    is_affirmative_confirmation,
    should_enable_tailor_selection,
)
from apps.workflows.chat_service import WorkflowChatService
from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus, WorkflowMessage
from apps.workflows.repositories import WorkflowRepository
from apps.workflows.services import WorkflowService


@pytest.fixture
def other_user(db):
    from apps.users.models import User

    return User.objects.create_user(
        email="other@example.com",
        password="testpass123",
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def completed_workflow(user):
    workflow = WorkflowRepository().create(
        user=user,
        name="Find remote Python roles",
        goal="Find remote Python backend jobs",
        status=WorkflowExecutionStatus.COMPLETED,
        context={
            "workflow_intent": "job_discovery",
            "preferences": {
                "target_roles": ["Python Engineer"],
                "target_locations": ["Remote"],
                "remote_preference": "remote",
            },
        },
        result={
            "workflow_intent": "job_discovery",
            "discovered_count": 3,
            "evaluated_count": 3,
            "accepted_count": 1,
            "borderline_count": 1,
            "rejected_count": 1,
            "top_match_score": 82,
        },
    )
    return workflow


@pytest.fixture
def evaluated_opportunities(user, completed_workflow):
    job_high = Job.objects.create(
        source="test",
        title="Senior Python Engineer",
        company="GoodCo",
        location="Remote",
        is_remote=True,
        description="Python backend",
        dedupe_key="dedupe-high",
    )
    job_rejected = Job.objects.create(
        source="test",
        title="Java Engineer",
        company="OtherCo",
        location="NYC",
        description="Java only",
        dedupe_key="dedupe-rejected",
    )
    job_borderline = Job.objects.create(
        source="test",
        title="Python Developer",
        company="MaybeCo",
        location="Remote",
        is_remote=True,
        description="Some Python",
        dedupe_key="dedupe-borderline",
    )
    high = Opportunity.objects.create(
        user=user,
        job=job_high,
        workflow_execution=completed_workflow,
        status=OpportunityStatus.DISCOVERED,
        match_score=82,
        evaluation={"gaps": [], "strengths": ["Python"]},
    )
    rejected = Opportunity.objects.create(
        user=user,
        job=job_rejected,
        workflow_execution=completed_workflow,
        status=OpportunityStatus.REJECTED,
        match_score=35,
        evaluation={"gaps": ["No Python overlap"]},
        match_context="Low skill overlap",
    )
    borderline = Opportunity.objects.create(
        user=user,
        job=job_borderline,
        workflow_execution=completed_workflow,
        status=OpportunityStatus.DISCOVERED,
        match_score=65,
        evaluation={"gaps": ["Limited PM experience"], "strengths": ["Python"]},
    )
    return {"high": high, "rejected": rejected, "borderline": borderline}


@pytest.fixture
def interviewing_application(user, evaluated_opportunities):
    application, _ = ApplicationRepository().create_from_opportunity(
        user, evaluated_opportunities["high"]
    )
    ApplicationRepository().update(
        application,
        stage=ApplicationStage.INTERVIEWING,
        stage_notes="Phone screen scheduled",
    )
    return application


@pytest.fixture
def interview_prep_workflow(user):
    workflow = WorkflowRepository().create(
        user=user,
        name="Google onsite prep",
        goal="Interview prep for my Google onsite",
        status=WorkflowExecutionStatus.COMPLETED,
        context={"workflow_intent": "interview_prep"},
        result={
            "workflow_intent": "interview_prep",
            "interview_plan_id": "plan-existing",
            "interview_prep_target_source": "application",
        },
    )
    return workflow


class TestFollowUpClassifier:
    def test_classify_rerun_remote(self):
        result = classify_follow_up("Show me more remote roles")
        assert result["intent"] == FOLLOW_UP_RERUN_SEARCH
        assert result["params"].get("remote_preference") == "remote"

    def test_classify_rejection_question(self):
        result = classify_follow_up("Why did you reject these?")
        assert result["intent"] == FOLLOW_UP_SHOW_REJECTED

    def test_classify_generic_question(self):
        result = classify_follow_up("What happened in this workflow?")
        assert result["intent"] == FOLLOW_UP_QUESTION

    def test_should_enable_tailor_selection_blocks_during_search_rerun(self, completed_workflow):
        completed_workflow.result = {
            **(completed_workflow.result or {}),
            "workflow_intent": "job_discovery",
            "search_rerun_in_progress": True,
        }
        assert (
            should_enable_tailor_selection(
                completed_workflow,
                completed_workflow.context or {},
                {},
            )
            is False
        )

    def test_classify_tailor_with_cover_letter(self):
        result = classify_follow_up(
            "tailor resume and cover letter for this job"
        )
        assert result["intent"] == FOLLOW_UP_TAILOR_RESUME
        assert result["params"].get("include_cover_letter") is True
        assert result["params"].get("pick") == "best"

    def test_classify_tailor_plain_no_best_pick(self):
        result = classify_follow_up("tailor resume")
        assert result["intent"] == FOLLOW_UP_TAILOR_RESUME
        assert "pick" not in result["params"]

    def test_classify_tailor_for_best_match_sets_pick(self):
        result = classify_follow_up("Tailor resume for best match")
        assert result["intent"] == FOLLOW_UP_TAILOR_RESUME
        assert result["params"].get("pick") == "best"

    def test_classify_list_jobs_to_select_for_tailor(self):
        result = classify_follow_up("list jobs to select for resume tailor")
        assert result["intent"] == FOLLOW_UP_TAILOR_RESUME
        assert "pick" not in result["params"]

    def test_is_affirmative_confirmation(self):
        assert is_affirmative_confirmation("yes")
        assert is_affirmative_confirmation("Yes, please")
        assert not is_affirmative_confirmation("yes, but only the resume")

    def test_classify_list_active_applications(self):
        result = classify_follow_up("list active job applications")
        assert result["intent"] == FOLLOW_UP_LIST_APPLICATIONS

    def test_classify_generate_interview_prep_for_applications(self):
        result = classify_follow_up("generate interview prep for active applications")
        assert result["intent"] == FOLLOW_UP_INTERVIEW_PREP
        assert result["params"].get("scope") == "application"

    def test_classify_view_prep_plan(self):
        result = classify_follow_up("View prep plan")
        assert result["intent"] == FOLLOW_UP_VIEW_INTERVIEW_PREP

    def test_classify_show_my_interview_prep_plan_views_not_generates(self):
        result = classify_follow_up("Show my interview prep plan")
        assert result["intent"] == FOLLOW_UP_VIEW_INTERVIEW_PREP

    def test_classify_open_interview_prep(self):
        result = classify_follow_up("open interview prep")
        assert result["intent"] == FOLLOW_UP_VIEW_INTERVIEW_PREP

    def test_classify_show_prep_plan(self):
        result = classify_follow_up("show prep plan")
        assert result["intent"] == FOLLOW_UP_VIEW_INTERVIEW_PREP

    def test_classify_add_interview(self):
        result = classify_follow_up(
            "Add interview for Staff Engineer at Acme on 2026-03-15"
        )
        assert result["intent"] == FOLLOW_UP_ADD_INTERVIEW
        assert result["params"]["company"] == "Acme"

    def test_classify_prepare_interviews_from_applications(self):
        result = classify_follow_up(
            "Prepare for interviews in the next two weeks from applications"
        )
        assert result["intent"] == FOLLOW_UP_INTERVIEW_PREP
        assert "goal" in result["params"]

    def test_classify_help_intent(self):
        result = classify_follow_up("what can you do?")
        assert result["intent"] == FOLLOW_UP_HELP
        assert result["params"].get("variant") == "help"

    def test_classify_greeting_intent(self):
        result = classify_follow_up("hello")
        assert result["intent"] == FOLLOW_UP_HELP
        assert result["params"].get("variant") == "greeting"

    def test_classify_off_topic_intent(self):
        result = classify_follow_up("what's 2+2?")
        assert result["intent"] == FOLLOW_UP_HELP
        assert result["params"].get("variant") == "off_topic"

    def test_classify_research_named_company(self):
        result = classify_follow_up("research namecheap company")
        assert result["intent"] == FOLLOW_UP_RESEARCH_COMPANY
        assert result["params"]["company_name"] == "namecheap"

    def test_classify_research_company_shorthand(self):
        result = classify_follow_up("research namecheap")
        assert result["intent"] == FOLLOW_UP_RESEARCH_COMPANY
        assert result["params"]["company_name"] == "namecheap"

    def test_classify_research_top_company_without_name(self):
        result = classify_follow_up("research company")
        assert result["intent"] == FOLLOW_UP_RESEARCH_COMPANY
        assert result["params"].get("company_name") is None
        assert result["params"].get("pick") == "best"

    def test_classify_learn_about_company(self):
        result = classify_follow_up("learn about stripe")
        assert result["intent"] == FOLLOW_UP_RESEARCH_COMPANY
        assert result["params"]["company_name"] == "stripe"

    def test_build_view_interview_prep_action(self):
        action = build_view_interview_prep_action("plan-123")
        assert action["key"] == FOLLOW_UP_VIEW_INTERVIEW_PREP
        assert action["requires_confirmation"] is False
        assert action["href"] == "/interviews?selected=plan-123"
        assert action["params"]["interview_plan_id"] == "plan-123"

    def test_build_tailored_resume_follow_up_actions(self):
        actions = build_tailored_resume_follow_up_actions("mat-456")
        assert len(actions) == 2
        assert actions[0]["key"] == FOLLOW_UP_VIEW_TAILORED_RESUME
        assert actions[0]["params"]["material_id"] == "mat-456"
        assert actions[0]["requires_confirmation"] is False
        assert actions[1]["key"] == FOLLOW_UP_DOWNLOAD_TAILORED_RESUME
        assert actions[1]["params"]["material_id"] == "mat-456"
        assert actions[1]["requires_confirmation"] is False

    def test_build_view_tailored_resume_action(self):
        action = build_view_tailored_resume_action("mat-789")
        assert action["key"] == FOLLOW_UP_VIEW_TAILORED_RESUME
        assert action["label"] == "View tailored resume"
        assert action["params"]["material_id"] == "mat-789"

    def test_build_cover_letter_follow_up_actions(self):
        actions = build_cover_letter_follow_up_actions("mat-cl-1")
        assert len(actions) == 2
        assert actions[0]["key"] == FOLLOW_UP_VIEW_COVER_LETTER
        assert actions[0]["params"]["material_id"] == "mat-cl-1"
        assert actions[1]["key"] == FOLLOW_UP_DOWNLOAD_COVER_LETTER

    def test_build_view_cover_letter_action(self):
        action = build_view_cover_letter_action("mat-cl-2")
        assert action["key"] == FOLLOW_UP_VIEW_COVER_LETTER
        assert action["label"] == "View cover letter"
        assert action["params"]["material_id"] == "mat-cl-2"


@pytest.mark.django_db
class TestContextualActions:
    def test_zero_discovery_job_search_cards(self, user):
        workflow = WorkflowRepository().create(
            user=user,
            name="Empty search",
            goal="Find roles",
            status=WorkflowExecutionStatus.COMPLETED,
            context={"workflow_intent": "job_discovery"},
            result={
                "workflow_intent": "job_discovery",
                "discovered_count": 0,
            },
        )
        cards = build_contextual_actions(
            workflow,
            {"best_opportunity": None, "sample_rejected": []},
            {"active_count": 0, "applications": []},
        )
        keys = [card["key"] for card in cards]
        assert FOLLOW_UP_RERUN_SEARCH in keys
        assert FOLLOW_UP_LIST_APPLICATIONS in keys
        assert FOLLOW_UP_INTERVIEW_PREP in keys
        assert len(cards) <= 4

    def test_job_discovery_with_matches_cards(
        self, completed_workflow, evaluated_opportunities
    ):
        cards = build_contextual_actions(
            completed_workflow,
            {
                "best_opportunity": {
                    "id": str(evaluated_opportunities["high"].id),
                    "title": "Senior Python Engineer",
                    "company": "GoodCo",
                    "match_score": 82,
                },
                "sample_rejected": [],
            },
            {"active_count": 0, "applications": []},
        )
        keys = [card["key"] for card in cards]
        assert FOLLOW_UP_RERUN_SEARCH in keys
        assert FOLLOW_UP_TAILOR_RESUME in keys
        assert len(cards) <= 4


@pytest.mark.django_db
class TestFollowUpReplies:
    def test_question_reply_does_not_mention_action_cards(
        self, completed_workflow, evaluated_opportunities
    ):
        from apps.workflows.follow_up import build_assistant_reply

        reply = build_assistant_reply(
            completed_workflow,
            intent=FOLLOW_UP_QUESTION,
            params={},
            workflow_context=completed_workflow.context or {},
            opportunities_summary={
                "best_opportunity": {
                    "title": "Senior Python Engineer",
                    "company": "GoodCo",
                    "match_score": 82,
                },
                "sample_rejected": [],
            },
            applications_summary={"active_count": 0, "applications": []},
        )
        assert "action card" not in reply.lower()
        assert "rerun search" in reply.lower() or "tailor" in reply.lower()


@pytest.fixture
def tailor_resume_workflow(user, evaluated_opportunities):
    workflow = WorkflowRepository().create(
        user=user,
        name="Tailor my resume for GoodCo",
        goal="Tailor my resume for GoodCo",
        status=WorkflowExecutionStatus.COMPLETED,
        context={"workflow_intent": "tailor_resume"},
        result={
            "workflow_intent": "tailor_resume",
            "tailored_material_id": "mat-existing",
            "selected_opportunity_id": str(evaluated_opportunities["high"].id),
        },
    )
    return workflow


@pytest.mark.django_db
class TestCompanyResearchChatRouting:
    def test_research_named_company_returns_action_card(
        self, api_client, user, tailor_resume_workflow, interviewing_application
    ):
        api_client.force_authenticate(user=user)
        url = reverse(
            "workflow-messages", kwargs={"workflow_id": tailor_resume_workflow.id}
        )
        response = api_client.post(
            url,
            {"content": "research namecheap company"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) == 1
        assert response.data["actions"][0]["key"] == FOLLOW_UP_RESEARCH_COMPANY
        assert response.data["actions"][0]["params"]["company_name"] == "namecheap"
        assert "namecheap" in response.data["assistant_message"]["content"].lower()
        assert "workflow" not in response.data["assistant_message"]["content"].lower() or (
            "is completed" not in response.data["assistant_message"]["content"].lower()
        )

    @patch("apps.workflows.chat_service.AgentExecutionSerializer")
    @patch("apps.workflows.chat_service.CompanyResearchAgent")
    def test_confirm_research_named_company_executes_agent(
        self,
        mock_agent_cls,
        mock_execution_serializer,
        api_client,
        user,
        tailor_resume_workflow,
    ):
        mock_execution_serializer.return_value.data = {"id": "exec-research"}
        mock_agent_cls.return_value.research.return_value = {
            "execution": MagicMock(id="exec-research"),
            "company_research": {
                "available": True,
                "summary": "Namecheap is a domain registrar and web hosting company.",
            },
            "reasoning_summary": "Researched Namecheap.",
        }

        api_client.force_authenticate(user=user)
        url = reverse(
            "workflow-messages", kwargs={"workflow_id": tailor_resume_workflow.id}
        )
        api_client.post(
            url,
            {"content": "research namecheap company"},
            format="json",
        )
        response = api_client.post(url, {"content": "yes"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get("confirmed") is True
        mock_agent_cls.return_value.research.assert_called_once()
        assert "namecheap" in response.data["assistant_message"]["content"].lower()
        assert "companies page" in response.data["assistant_message"]["content"].lower()

    @patch("apps.workflows.chat_service.AgentExecutionSerializer")
    @patch("apps.workflows.chat_service.CompanyResearchAgent")
    def test_research_matches_existing_opportunity_company(
        self,
        mock_agent_cls,
        mock_execution_serializer,
        api_client,
        user,
        completed_workflow,
        evaluated_opportunities,
    ):
        mock_execution_serializer.return_value.data = {"id": "exec-research"}
        mock_agent_cls.return_value.research.return_value = {
            "execution": MagicMock(id="exec-research"),
            "company_research": {
                "available": True,
                "summary": "GoodCo builds Python backends.",
            },
            "reasoning_summary": "Researched GoodCo.",
        }

        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        api_client.post(url, {"content": "research goodco"}, format="json")
        response = api_client.post(url, {"content": "yes"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        call_args = mock_agent_cls.return_value.research.call_args
        researched_opportunity = call_args[0][1]
        assert researched_opportunity.job.company == "GoodCo"


@pytest.mark.django_db
class TestWorkflowMessagesApi:
    def test_list_messages_empty(self, api_client, user, completed_workflow):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["messages"] == []

    def test_post_message_persists_and_returns_actions(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "Show me more remote roles"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user_message"]["role"] == "user"
        assert response.data["assistant_message"]["role"] == "assistant"
        assert len(response.data["actions"]) == 1
        assert response.data["actions"][0]["key"] == FOLLOW_UP_RERUN_SEARCH
        assert WorkflowMessage.objects.filter(workflow=completed_workflow).count() == 2
        assistant = WorkflowMessage.objects.filter(
            workflow=completed_workflow,
            role="assistant",
        ).latest("created_at")
        assert assistant.metadata["routing"]["follow_up_intent"] == FOLLOW_UP_RERUN_SEARCH
        assert assistant.metadata["routing"]["method"] == "rule_based"

    def test_question_answer_with_contextual_actions(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "What were the evaluation results?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) == 2
        assert "rejected" in response.data["assistant_message"]["content"].lower()

    def test_help_intent_returns_contextual_actions(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "what can you do?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) >= 2
        assert len(response.data["actions"]) <= 4
        assert "here's what i can help" in response.data["assistant_message"]["content"].lower()

    def test_greeting_returns_welcome_style_reply_with_actions(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(url, {"content": "hello"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) >= 1
        assert "hi!" in response.data["assistant_message"]["content"].lower()

    def test_off_topic_redirect_returns_help_cards(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "what's 2+2?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) >= 1
        assert "career workflow assistant" in response.data["assistant_message"]["content"].lower()

    def test_list_applications_returns_summary_without_actions(
        self, api_client, user, completed_workflow, interviewing_application
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "list active job applications"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["actions"] == []
        content = response.data["assistant_message"]["content"].lower()
        assert "application" in content
        assert "senior python engineer" in content
        assert "action card" not in content

    def test_interview_prep_request_returns_action_card(
        self, api_client, user, completed_workflow, interviewing_application
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "generate interview prep for active applications"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) == 1
        assert response.data["actions"][0]["key"] == FOLLOW_UP_INTERVIEW_PREP
        assert "action card" in response.data["assistant_message"]["content"].lower()

    def test_add_interview_request_returns_action_card(
        self, api_client, user, completed_workflow
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "Add interview for Staff Engineer at Acme on 2026-03-15"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["actions"]) == 1
        assert response.data["actions"][0]["key"] == FOLLOW_UP_ADD_INTERVIEW
        assert response.data["actions"][0]["params"]["company"] == "Acme"

    def test_add_interview_execute_action(
        self, api_client, user, completed_workflow
    ):
        from apps.applications.models import Interview

        api_client.force_authenticate(user=user)
        action_url = reverse(
            "workflow-actions",
            kwargs={"workflow_id": completed_workflow.id},
        )
        response = api_client.post(
            action_url,
            {
                "action_key": FOLLOW_UP_ADD_INTERVIEW,
                "params": {
                    "company": "Acme",
                    "job_title": "Staff Engineer",
                    "round_label": "Technical",
                },
                "confirmed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert Interview.objects.filter(user=user).count() == 1
        assert "staff engineer" in response.data["assistant_message"]["content"].lower()

    def test_interview_prep_on_completed_prep_workflow(
        self, api_client, user, interview_prep_workflow, interviewing_application
    ):
        api_client.force_authenticate(user=user)
        url = reverse(
            "workflow-messages", kwargs={"workflow_id": interview_prep_workflow.id}
        )
        response = api_client.post(
            url,
            {"content": "generate interview prep for active applications"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["actions"][0]["key"] == FOLLOW_UP_INTERVIEW_PREP

    def test_view_prep_plan_with_existing_plan_returns_view_action(
        self, api_client, user, interview_prep_workflow
    ):
        api_client.force_authenticate(user=user)
        url = reverse(
            "workflow-messages", kwargs={"workflow_id": interview_prep_workflow.id}
        )
        response = api_client.post(url, {"content": "View prep plan"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["actions"][0]["key"] == FOLLOW_UP_VIEW_INTERVIEW_PREP
        assert response.data["actions"][0]["params"]["interview_plan_id"] == "plan-existing"
        assert "ready" in response.data["assistant_message"]["content"].lower()
        assistant = WorkflowMessage.objects.filter(
            workflow=interview_prep_workflow, role="assistant"
        ).latest("created_at")
        assert assistant.metadata["routing"]["follow_up_intent"] == FOLLOW_UP_VIEW_INTERVIEW_PREP

    def test_view_prep_plan_without_plan_offers_generate(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(url, {"content": "View prep plan"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["actions"][0]["key"] == FOLLOW_UP_INTERVIEW_PREP
        assert "no prep plan" in response.data["assistant_message"]["content"].lower()
        assert "49" not in response.data["assistant_message"]["content"]
        assert "discovered" not in response.data["assistant_message"]["content"].lower()

    @patch("apps.workflows.chat_service.invoke_workflow_tool")
    def test_yes_confirms_pending_interview_prep_action(
        self,
        mock_invoke_tool,
        api_client,
        user,
        completed_workflow,
        interviewing_application,
    ):
        from apps.workflows.tool_registry import ToolResult

        mock_invoke_tool.return_value = ToolResult(
            tool="interview_prep",
            success=True,
            summary="Interview prep plan ready.",
            data={"interview_plan_id": "plan-new"},
        )

        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        api_client.post(
            url,
            {"content": "generate interview prep for active applications"},
            format="json",
        )

        response = api_client.post(url, {"content": "yes"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get("confirmed") is True
        mock_invoke_tool.assert_called_once()
        assert "Interview prep plan ready." in response.data["assistant_message"]["content"]
        assert response.data["actions"][0]["key"] == FOLLOW_UP_VIEW_INTERVIEW_PREP
        assert response.data["actions"][0]["href"] == "/interviews?selected=plan-new"

    @patch("apps.workflows.chat_service.AgentExecutionSerializer")
    @patch("apps.workflows.chat_service.ApplicationMaterialSerializer")
    @patch("apps.workflows.chat_service.ResumeTailorAgent")
    def test_yes_confirms_pending_tailor_resume_action(
        self,
        mock_tailor_cls,
        mock_material_serializer,
        mock_execution_serializer,
        api_client,
        user,
        completed_workflow,
        evaluated_opportunities,
    ):
        mock_material_serializer.return_value.data = {"id": "mat-solo"}
        mock_execution_serializer.return_value.data = {"id": "exec-solo"}
        mock_material = MagicMock()
        mock_material.id = "mat-solo"
        mock_execution = MagicMock()
        mock_tailor_cls.return_value.tailor.return_value = {
            "material": mock_material,
            "execution": mock_execution,
            "reasoning_summary": "Tailored resume for Lead Software Engineer.",
        }

        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        api_client.post(
            url,
            {"content": "tailor resume for best match"},
            format="json",
        )

        response = api_client.post(url, {"content": "yes"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get("confirmed") is True
        mock_tailor_cls.return_value.tailor.assert_called_once()
        action_keys = [action["key"] for action in response.data["actions"]]
        assert action_keys == [
            FOLLOW_UP_VIEW_TAILORED_RESUME,
            FOLLOW_UP_DOWNLOAD_TAILORED_RESUME,
        ]
        assert response.data["actions"][0]["params"]["material_id"] == "mat-solo"
        completed_workflow.refresh_from_db()
        assert completed_workflow.result["tailored_material_id"] == "mat-solo"

    def test_yes_without_pending_actions_explains_next_steps(
        self, api_client, user, completed_workflow
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(url, {"content": "yes"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["actions"] == []
        assert "nothing waiting for confirmation" in response.data["assistant_message"]["content"].lower()
        assert "interview prep" in response.data["assistant_message"]["content"].lower()

    def test_ownership_isolation(self, api_client, other_user, completed_workflow):
        api_client.force_authenticate(user=other_user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(url, {"content": "hello"}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_tailor_request_returns_resume_and_cover_letter_actions(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "tailor resume and cover letter for this job"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        keys = [action["key"] for action in response.data["actions"]]
        assert keys == [FOLLOW_UP_TAILOR_RESUME, FOLLOW_UP_COVER_LETTER]
        assert "resume and cover letter" in response.data["assistant_message"]["content"]

    def test_tailor_after_job_discovery_shows_selection_not_auto_top_match(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(url, {"content": "tailor resume"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "pick a role below" in response.data["assistant_message"]["content"].lower()
        assert "top match:" not in response.data["assistant_message"]["content"].lower()
        assert not any(
            action.get("label") == "Tailor resume for best match"
            for action in response.data["actions"]
        )

        assert "workflow" in response.data
        assistant = response.data["assistant_message"]
        assert assistant["metadata"]["tailor_selection"]["pending"] is True
        assert assistant["metadata"]["tailor_selection"]["tailor_options"]["opportunities"]
        completed_workflow.refresh_from_db()
        assert completed_workflow.result["tailor_selection_pending"] is True
        tailor_options = completed_workflow.result["tailor_options"]
        assert len(tailor_options["opportunities"]) >= 1
        option_ids = {option["id"] for option in tailor_options["opportunities"]}
        assert str(evaluated_opportunities["high"].id) in option_ids
        assert str(evaluated_opportunities["borderline"].id) in option_ids

    def test_list_jobs_phrase_enables_tailor_selection(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "list jobs to select for resume tailor"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "pick a role below" in response.data["assistant_message"]["content"].lower()
        completed_workflow.refresh_from_db()
        assert completed_workflow.result["tailor_selection_pending"] is True

    def test_tailor_for_best_match_still_auto_picks_top(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"content": "Tailor resume for best match"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "top match:" in response.data["assistant_message"]["content"].lower()
        assert "workflow" not in response.data
        completed_workflow.refresh_from_db()
        assert completed_workflow.result.get("tailor_selection_pending") is not True

    @patch("apps.workflows.chat_service.AgentExecutionSerializer")
    @patch("apps.workflows.chat_service.ApplicationMaterialSerializer")
    @patch("apps.workflows.chat_service.CoverLetterAgent")
    @patch("apps.workflows.chat_service.ResumeTailorAgent")
    def test_yes_confirms_pending_tailor_actions(
        self,
        mock_tailor_cls,
        mock_cover_cls,
        mock_material_serializer,
        mock_execution_serializer,
        api_client,
        user,
        completed_workflow,
        evaluated_opportunities,
    ):
        mock_material_serializer.return_value.data = {"id": "mat-1"}
        mock_execution_serializer.return_value.data = {"id": "exec-1"}
        mock_material = MagicMock()
        mock_material.id = "mat-tailor-1"
        mock_cover_material = MagicMock()
        mock_cover_material.id = "mat-cover-1"
        mock_execution = MagicMock()
        mock_execution.id = evaluated_opportunities["high"].id
        mock_tailor_cls.return_value.tailor.return_value = {
            "material": mock_material,
            "execution": mock_execution,
            "reasoning_summary": "Tailored resume ready.",
        }
        mock_cover_cls.return_value.generate.return_value = {
            "material": mock_cover_material,
            "execution": mock_execution,
            "reasoning_summary": "Cover letter ready.",
        }

        api_client.force_authenticate(user=user)
        url = reverse("workflow-messages", kwargs={"workflow_id": completed_workflow.id})
        api_client.post(
            url,
            {"content": "tailor resume and cover letter for this job"},
            format="json",
        )

        response = api_client.post(url, {"content": "yes"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get("confirmed") is True
        assert "system_message" in response.data
        mock_tailor_cls.return_value.tailor.assert_called_once()
        mock_cover_cls.return_value.generate.assert_called_once()
        assert "Tailored resume ready." in response.data["assistant_message"]["content"]
        assert "Cover letter ready." in response.data["assistant_message"]["content"]

        action_keys = [action["key"] for action in response.data["actions"]]
        assert FOLLOW_UP_VIEW_TAILORED_RESUME in action_keys
        assert FOLLOW_UP_DOWNLOAD_TAILORED_RESUME in action_keys
        view_action = next(
            action for action in response.data["actions"]
            if action["key"] == FOLLOW_UP_VIEW_TAILORED_RESUME
        )
        assert view_action["params"]["material_id"] == "mat-tailor-1"
        assert FOLLOW_UP_VIEW_COVER_LETTER in action_keys
        assert FOLLOW_UP_DOWNLOAD_COVER_LETTER in action_keys
        cover_view = next(
            action for action in response.data["actions"]
            if action["key"] == FOLLOW_UP_VIEW_COVER_LETTER
        )
        assert cover_view["params"]["material_id"] == "mat-cover-1"
        completed_workflow.refresh_from_db()
        assert completed_workflow.result["cover_letter_material_id"] == "mat-cover-1"

        pending_confirmations = WorkflowMessage.objects.filter(
            workflow=completed_workflow,
            role="assistant",
        ).exclude(actions=[]).exclude(id=response.data["assistant_message"]["id"])
        assert pending_confirmations.count() == 0


@pytest.mark.django_db
class TestWorkflowActionsApi:
    def test_action_requires_confirmation(self, api_client, user, completed_workflow):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {"action_key": FOLLOW_UP_RERUN_SEARCH, "params": {}, "confirmed": False},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch.object(WorkflowService, "rerun_job_search")
    def test_rerun_search_action(
        self, mock_rerun, api_client, user, completed_workflow, evaluated_opportunities
    ):
        mock_rerun.return_value = {
            "discovered_count": 2,
            "evaluated_count": 2,
            "accepted_count": 1,
            "borderline_count": 0,
            "rejected_count": 1,
            "top_match_score": 75,
            "workflow": {"id": str(completed_workflow.id)},
            "job_search_execution": {},
            "provider_summary": {"providers": {}},
            "job_search_summary": "found roles",
            "evaluation_executions": [],
        }
        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {
                "action_key": FOLLOW_UP_RERUN_SEARCH,
                "params": {"remote_preference": "remote"},
                "confirmed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_rerun.assert_called_once()
        _, kwargs = mock_rerun.call_args
        assert kwargs["overrides"]["remote_preference"] == "remote"
        assert WorkflowMessage.objects.filter(
            workflow=completed_workflow, role="system"
        ).exists()

    def test_show_rejected_action(
        self, api_client, user, completed_workflow, evaluated_opportunities
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {
                "action_key": FOLLOW_UP_SHOW_REJECTED,
                "params": {"include_rejected": True},
                "confirmed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        completed_workflow.refresh_from_db()
        assert completed_workflow.context["refinement"]["include_rejected"] is True
        assistant = response.data["assistant_message"]
        refinement_result = assistant["metadata"]["refinement_result"]
        assert refinement_result["kind"] == "rejected"
        assert refinement_result["count"] == 1
        assert len(refinement_result["opportunities"]) == 1
        assert (
            refinement_result["opportunities"][0]["id"]
            == str(evaluated_opportunities["rejected"].id)
        )
        assert len(response.data["result"]["opportunities"]) == 1

    def test_list_applications_action(
        self, api_client, user, completed_workflow, interviewing_application
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {
                "action_key": FOLLOW_UP_LIST_APPLICATIONS,
                "params": {},
                "confirmed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        content = response.data["assistant_message"]["content"].lower()
        assert "application" in content
        assert "senior python engineer" in content
        assert WorkflowMessage.objects.filter(
            workflow=completed_workflow, role="system"
        ).exists()

    @patch("apps.workflows.chat_service.AgentExecutionSerializer")
    @patch("apps.workflows.chat_service.ApplicationMaterialSerializer")
    @patch("apps.workflows.chat_service.ResumeTailorAgent")
    def test_tailor_action(
        self,
        mock_agent_cls,
        mock_material_serializer,
        mock_execution_serializer,
        api_client,
        user,
        completed_workflow,
        evaluated_opportunities,
    ):
        mock_material_serializer.return_value.data = {
            "id": str(evaluated_opportunities["high"].id),
            "material_type": "tailored_resume",
        }
        mock_execution_serializer.return_value.data = {
            "id": str(evaluated_opportunities["high"].id),
            "agent_name": "resume_tailor",
        }
        mock_material = MagicMock()
        mock_material.id = evaluated_opportunities["high"].id
        mock_execution = MagicMock()
        mock_execution.id = evaluated_opportunities["high"].id
        mock_agent_cls.return_value.tailor.return_value = {
            "material": mock_material,
            "execution": mock_execution,
            "reasoning_summary": "Tailored resume ready.",
        }

        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {
                "action_key": "tailor_resume",
                "params": {"pick": "best"},
                "confirmed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_agent_cls.return_value.tailor.assert_called_once()
        action_keys = [
            action["key"] for action in response.data["assistant_message"]["actions"]
        ]
        assert FOLLOW_UP_VIEW_TAILORED_RESUME in action_keys
        assert FOLLOW_UP_DOWNLOAD_TAILORED_RESUME in action_keys

        pending_confirmations = WorkflowMessage.objects.filter(
            workflow=completed_workflow,
            role="assistant",
        ).exclude(actions=[]).exclude(id=response.data["assistant_message"]["id"])
        assert pending_confirmations.count() == 0

    def test_tailor_action_enables_selection_with_message_metadata(
        self,
        api_client,
        user,
        completed_workflow,
        evaluated_opportunities,
    ):
        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {
                "action_key": FOLLOW_UP_TAILOR_RESUME,
                "params": {},
                "confirmed": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        metadata = response.data["assistant_message"]["metadata"]["tailor_selection"]
        assert metadata["pending"] is True
        assert metadata["tailor_options"]["opportunities"]
        completed_workflow.refresh_from_db()
        assert completed_workflow.result["tailor_selection_pending"] is True

    @patch("apps.workflows.chat_service.AgentExecutionSerializer")
    @patch("apps.workflows.chat_service.ApplicationMaterialSerializer")
    @patch("apps.workflows.chat_service.CoverLetterAgent")
    def test_cover_letter_action(
        self,
        mock_agent_cls,
        mock_material_serializer,
        mock_execution_serializer,
        api_client,
        user,
        completed_workflow,
        evaluated_opportunities,
    ):
        mock_material_serializer.return_value.data = {
            "id": "mat-cover-api",
            "material_type": "cover_letter",
        }
        mock_execution_serializer.return_value.data = {
            "id": str(evaluated_opportunities["high"].id),
            "agent_name": "cover_letter",
        }
        mock_material = MagicMock()
        mock_material.id = "mat-cover-api"
        mock_execution = MagicMock()
        mock_execution.id = evaluated_opportunities["high"].id
        mock_agent_cls.return_value.generate.return_value = {
            "material": mock_material,
            "execution": mock_execution,
            "reasoning_summary": "Cover letter ready.",
        }

        api_client.force_authenticate(user=user)
        url = reverse("workflow-actions", kwargs={"workflow_id": completed_workflow.id})
        response = api_client.post(
            url,
            {
                "action_key": FOLLOW_UP_COVER_LETTER,
                "params": {"pick": "best"},
                "confirmed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        action_keys = [
            action["key"] for action in response.data["assistant_message"]["actions"]
        ]
        assert FOLLOW_UP_VIEW_COVER_LETTER in action_keys
        assert FOLLOW_UP_DOWNLOAD_COVER_LETTER in action_keys
        completed_workflow.refresh_from_db()
        assert completed_workflow.result["cover_letter_material_id"] == "mat-cover-api"


@pytest.mark.django_db
class TestWelcomeSeed:
    def test_seed_welcome_message_once(self, user, completed_workflow, evaluated_opportunities):
        chat_service = WorkflowChatService()
        first = chat_service.seed_welcome_message(user, completed_workflow)
        second = chat_service.seed_welcome_message(user, completed_workflow)

        assert first is not None
        assert second is None
        assert first.role == "assistant"
        assert len(first.actions) >= 1
        assert WorkflowMessage.objects.filter(
            workflow=completed_workflow,
            role="assistant",
        ).count() == 1

    def test_seed_welcome_message_tailor_pending_avoids_duplicate_next_action(self, user):
        workflow = WorkflowRepository().create(
            user=user,
            name="Tailor resume for fintech",
            goal="Tailor my resume for staff engineer positions in fintech",
            status=WorkflowExecutionStatus.COMPLETED,
            context={"workflow_intent": "tailor_resume"},
            result={
                "workflow_intent": "tailor_resume",
                "tailor_selection_pending": True,
                "next_action": "Select a saved or high-match role below to tailor your resume.",
            },
        )
        chat_service = WorkflowChatService()
        welcome = chat_service.seed_welcome_message(user, workflow)

        assert welcome is not None
        assert "Select a saved or high-match role below" not in welcome.content
        assert "Pick a role below to tailor your resume" in welcome.content
        assert welcome.metadata["tailor_selection"]["pending"] is True

    @patch("apps.workflows.services.MemoryService.record_workflow_context")
    @patch("apps.workflows.services.ActivityService.record_workflow_started")
    @patch("apps.workflows.services.JobEvaluationAgent")
    @patch("apps.workflows.services.JobSearchAgent")
    @patch("apps.workflows.services.PlannerAgent")
    def test_execute_workflow_seeds_welcome_message(
        self,
        mock_planner_cls,
        mock_search_cls,
        mock_eval_cls,
        mock_activity,
        mock_memory,
        user,
    ):
        workflow = WorkflowRepository().create(
            user=user,
            name="Find backend roles",
            goal="Find backend engineer roles",
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )
        mock_planner = mock_planner_cls.return_value
        mock_planner.plan.return_value = {
            "context": {"preferences": {"target_roles": ["Backend Engineer"]}},
            "plan_summary": "Search for backend roles.",
            "suggested_steps": ["Run job search"],
            "planned_agents": ["planner", "job_search", "job_evaluation"],
            "execution": MagicMock(),
        }
        mock_search_cls.return_value.search.return_value = {
            "discovered_count": 0,
            "provider_summary": {"providers": {}},
            "reasoning_summary": "No roles found.",
            "execution": MagicMock(),
        }
        mock_eval_cls.return_value.evaluate = MagicMock()

        service = WorkflowService(
            planner=mock_planner,
            job_search_agent=mock_search_cls.return_value,
            evaluation_agent=mock_eval_cls.return_value,
        )
        service._evaluate_discovered_opportunities = MagicMock(
            return_value={
                "evaluated_count": 0,
                "accepted_count": 0,
                "borderline_count": 0,
                "rejected_count": 0,
                "top_match_score": 0,
                "evaluation_executions": [],
            }
        )

        service.execute_workflow(user, workflow, goal="Find backend engineer roles")

        welcome = WorkflowMessage.objects.filter(
            workflow=workflow,
            role="assistant",
        ).first()
        assert welcome is not None
        assert len(welcome.actions) >= 1
        keys = [action["key"] for action in welcome.actions]
        assert FOLLOW_UP_RERUN_SEARCH in keys
        assert FOLLOW_UP_LIST_APPLICATIONS in keys

    def test_seed_welcome_message_defaults_metadata(self, user, completed_workflow):
        chat_service = WorkflowChatService()
        welcome = chat_service.seed_welcome_message(user, completed_workflow)

        assert welcome is not None
        assert welcome.metadata == {}
        assert WorkflowMessage.objects.filter(
            workflow=completed_workflow,
            role="assistant",
            metadata__isnull=True,
        ).count() == 0


@pytest.mark.django_db
class TestRerunSearchOverrides:
    def test_rerun_stores_overrides_in_result(self, user, completed_workflow):
        mock_search = MagicMock()
        mock_search.search.return_value = {
            "execution": MagicMock(),
            "discovered_count": 1,
            "provider_summary": {"providers": {}},
            "reasoning_summary": "search done",
        }
        service = WorkflowService(job_search_agent=mock_search)
        service._evaluate_discovered_opportunities = MagicMock(
            return_value={
                "evaluated_count": 0,
                "accepted_count": 0,
                "borderline_count": 0,
                "rejected_count": 0,
                "top_match_score": 0,
                "evaluation_executions": [],
            }
        )

        with patch("apps.workflows.services.dispatch_rerun_job_search"):
            service.rerun_job_search(
                user,
                completed_workflow.id,
                overrides={"remote_preference": "remote", "query": "staff engineer"},
            )

        completed_workflow.refresh_from_db()
        assert completed_workflow.status == WorkflowExecutionStatus.RUNNING
        assert completed_workflow.context["search_overrides"]["remote_preference"] == "remote"
        assert completed_workflow.result["search_rerun_in_progress"] is True
        assert completed_workflow.result["tailor_selection_pending"] is False
        assert "tailor_options" not in completed_workflow.result

        from apps.workflows.tool_registry import ToolResult

        mock_registry = MagicMock()
        mock_registry.get.return_value = MagicMock(auto_run=True, requires_confirmation=False)
        mock_registry.agent_name_for.side_effect = lambda key: key
        mock_registry.execute.side_effect = [
            ToolResult(
                tool="job_search",
                success=True,
                summary="search done",
                data={
                    "discovered_count": 1,
                    "provider_summary": {"providers": {}},
                    "job_search_summary": "search done",
                },
                execution=MagicMock(),
            ),
            ToolResult(
                tool="job_evaluation",
                success=True,
                summary="evaluated",
                data={
                    "evaluated_count": 0,
                    "accepted_count": 0,
                    "borderline_count": 0,
                    "rejected_count": 0,
                    "top_match_score": 0,
                    "evaluation_executions": [],
                },
            ),
        ]
        mock_registry.merge_result.side_effect = lambda workflow, tool_key, tool_result: None
        service._tool_registry = mock_registry

        service._execute_rerun_job_search(
            user,
            completed_workflow,
            overrides={"remote_preference": "remote", "query": "staff engineer"},
        )

        completed_workflow.refresh_from_db()
        assert completed_workflow.context["search_overrides"]["remote_preference"] == "remote"
        assert completed_workflow.result["last_search_overrides"]["query"] == "staff engineer"
        assert completed_workflow.result["search_rerun_in_progress"] is False
