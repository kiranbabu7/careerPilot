"""Tests for shared application material context helpers."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.agents.material_context import build_prompt_variables
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.models import Resume
from apps.users.models import UserPreference
from apps.workflows.models import WorkflowExecution

pytest_plugins = ["apps.resumes.tests.test_phase2"]


@pytest.fixture
def workflow(user):
    return WorkflowExecution.objects.create(
        user=user,
        name="Test workflow",
        goal="Find backend roles",
        status="completed",
    )


@pytest.fixture
def job():
    return Job.objects.create(
        external_id="ext-material-context",
        source="linkedin",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        description="Python Django",
        dedupe_key="dedupe-material-context",
    )


@pytest.fixture
def opportunity(user, workflow, job):
    return Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.SAVED,
        evaluation={"match_score": 80, "rationale": "Good fit"},
    )


@pytest.fixture
def active_resume(user):
    return Resume.objects.create(
        user=user,
        file=SimpleUploadedFile("resume.txt", b"resume"),
        original_filename="resume.txt",
        content_type="text/plain",
        file_size=6,
        extracted_text=(
            "Jane Doe\n\nWORK EXPERIENCE\n"
            "Software Engineer --- Acme Corp\n"
            "Jan 2022 -- Present\n"
        ),
        is_active=True,
    )


@pytest.fixture
def preferences(user):
    pref, _ = UserPreference.objects.get_or_create(user=user)
    pref.target_roles = ["Backend Engineer"]
    pref.target_locations = ["Remote"]
    pref.remote_preference = "remote"
    pref.skills = ["Python"]
    pref.career_goals = "Staff engineer role"
    pref.save()
    return pref


@pytest.mark.django_db
class TestBuildPromptVariables:
    def test_includes_years_of_experience_constraint(
        self, user, opportunity, active_resume, preferences
    ):
        variables = build_prompt_variables(
            {
                "job": opportunity.job,
                "preferences": preferences,
                "evaluation": opportunity.evaluation,
                "resume_analysis": None,
                "active_resume": active_resume,
                "company_research": {},
            }
        )
        assert "years_of_experience" in variables
        assert "MUST NOT claim more than" in variables["years_of_experience"]
