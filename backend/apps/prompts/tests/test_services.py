"""Phase 6 prompt service tests."""

import pytest

from apps.prompts.models import PromptVersion
from apps.prompts.services import (
    MissingPromptVariablesError,
    PromptNotFoundError,
    PromptService,
)


@pytest.mark.django_db
class TestPromptService:
    def test_renders_from_filesystem_when_no_db_prompt(self):
        service = PromptService()
        result = service.render(
            "resume_tailor",
            {
                "job_title": "Engineer",
                "job_company": "Acme",
                "job_location": "Remote",
                "is_remote": "Yes",
                "job_description": "Build APIs",
                "match_evaluation": "Score 85",
                "company_research": "Growing company",
                "target_roles": "Engineer",
                "target_locations": "Remote",
                "remote_preference": "remote",
                "skills": "Python",
                "career_goals": "Staff role",
                "resume_analysis": "Strong backend profile",
                "resume_text": "Jane Doe\nPython developer",
                "years_of_experience": (
                    "4 years total (computed from employment dates in the source resume). "
                    "You MUST NOT claim more than 4 years of professional experience."
                ),
            },
        )
        assert result["name"] == "resume_tailor"
        assert result["version"] == 1
        assert result["source"] == "filesystem"
        assert "Jane Doe" in result["rendered_text"]
        assert "Acme" in result["rendered_text"]
        assert "NEVER fabricate or inflate years" in result["rendered_text"]
        assert "MUST NOT claim more than 4 years" in result["rendered_text"]

    def test_prefers_active_db_prompt(self):
        PromptVersion.objects.create(
            name="resume_tailor",
            version=2,
            template="DB prompt for {job_title} at {job_company}. Resume: {resume_text}",
            is_active=True,
        )
        service = PromptService()
        result = service.render(
            "resume_tailor",
            {
                "job_title": "Engineer",
                "job_company": "Acme",
                "resume_text": "Jane",
            },
        )
        assert result["version"] == 2
        assert result["source"] == "db"
        assert result["rendered_text"].startswith("DB prompt")

    def test_raises_for_missing_variables(self):
        service = PromptService()
        with pytest.raises(MissingPromptVariablesError) as exc_info:
            service.render("resume_tailor", {"job_title": "Only one"})
        assert "job_company" in exc_info.value.missing

    def test_raises_for_unknown_prompt(self):
        service = PromptService()
        with pytest.raises(PromptNotFoundError):
            service.render(
                "nonexistent_prompt",
                {"foo": "bar"},
            )

    def test_planner_template_loads(self):
        service = PromptService()
        result = service.render(
            "planner",
            {
                "goal": "Find remote senior backend roles at growth-stage startups",
                "workflow_intent": "job_discovery",
                "target_roles": "Senior Backend Engineer",
                "target_locations": "Remote",
                "remote_preference": "remote",
                "skills": "Python, Django",
                "career_goals": "Staff engineer",
                "active_resume": "resume.pdf (health 80)",
                "memory_snippets": "- prefers startups",
                "pipeline_summary": "0 applications, 0 materials, 0 interview plans",
            },
        )
        assert result["source"] == "filesystem"
        assert "growth-stage" in result["rendered_text"].lower()

    def test_cover_letter_template_loads(self):
        service = PromptService()
        result = service.render(
            "cover_letter",
            {
                "job_title": "Engineer",
                "job_company": "Acme",
                "job_location": "Remote",
                "is_remote": "Yes",
                "job_description": "Build APIs",
                "match_evaluation": "Score 85",
                "company_research": "Growing company",
                "target_roles": "Engineer",
                "target_locations": "Remote",
                "remote_preference": "remote",
                "skills": "Python",
                "career_goals": "Staff role",
                "resume_analysis": "Strong backend profile",
                "resume_text": "Jane Doe",
                "tailored_resume": "Tailored content",
                "candidate_name": "Jane Doe",
                "candidate_email": "jane@example.com",
                "candidate_phone": "555-0100",
                "candidate_location": "Remote",
                "letter_date": "June 29, 2026",
            },
        )
        assert result["source"] == "filesystem"
        assert "Tailored content" in result["rendered_text"]
        assert "Jane Doe" in result["rendered_text"]
        assert "body only" in result["rendered_text"].lower()
