"""Phase 6 tests — application materials, agents, and APIs."""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.agents.cover_letter import COVER_LETTER_AGENT_NAME, CoverLetterAgent
from apps.agents.material_context import NoActiveResumeError
from apps.agents.models import AgentExecution
from apps.agents.resume_tailoring import RESUME_TAILOR_AGENT_NAME, ResumeTailorAgent
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.resumes.materials_provider import (
    ApplicationMaterialsProvider,
    MaterialGenerationResult,
)
from apps.resumes.models import ApplicationMaterial, Resume
from apps.resumes.pdf_export import (
    generate_ats_resume_pdf,
    generate_cover_letter_pdf,
    plain_text_from_markdown,
)
from apps.resumes.tests.test_phase2 import user
from apps.users.models import UserPreference
from apps.users.models import User
from apps.workflows.models import WorkflowExecution


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def workflow(user):
    return WorkflowExecution.objects.create(
        user=user,
        name="Test workflow",
        goal="Find senior backend roles",
        status="completed",
    )


@pytest.fixture
def job():
    return Job.objects.create(
        external_id="ext-phase6",
        source="linkedin",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        salary_min=130000,
        salary_max=170000,
        description="Python Django PostgreSQL AWS Kubernetes",
        dedupe_key="dedupe-acme-phase6",
        company_research={"available": True, "summary": "Acme is growing fast."},
    )


@pytest.fixture
def opportunity(user, workflow, job):
    return Opportunity.objects.create(
        user=user,
        job=job,
        workflow_execution=workflow,
        status=OpportunityStatus.SAVED,
        match_score=85,
        evaluation={
            "match_score": 85,
            "recommendation": "strong_match",
            "rationale": "Strong Python and Django alignment.",
            "strengths": ["Python", "Django"],
            "gaps": ["Kubernetes depth"],
        },
    )


@pytest.fixture
def active_resume(user):
    return Resume.objects.create(
        user=user,
        file=SimpleUploadedFile("resume.txt", b"Jane Doe\nSenior Python Engineer"),
        original_filename="resume.txt",
        content_type="text/plain",
        file_size=32,
        extracted_text="Jane Doe\nSenior Python Engineer with Django and AWS experience.",
        is_active=True,
    )


@pytest.fixture
def preferences(user):
    pref, _ = UserPreference.objects.get_or_create(user=user)
    pref.target_roles = ["Senior Backend Engineer"]
    pref.target_locations = ["Remote"]
    pref.remote_preference = "remote"
    pref.skills = ["Python", "Django", "PostgreSQL"]
    pref.career_goals = "Land a staff backend role"
    pref.save()
    return pref


@pytest.mark.django_db
class TestApplicationMaterialModel:
    def test_persists_material(self, user, opportunity, active_resume):
        material = ApplicationMaterial.objects.create(
            user=user,
            opportunity=opportunity,
            source_resume=active_resume,
            material_type="tailored_resume",
            content="# Tailored resume\n\nContent here.",
            prompt_name="resume_tailor",
            prompt_version=1,
            model_name="local-fallback",
            metadata={"used_fallback": True},
        )
        assert material.opportunity.job.title == "Senior Backend Engineer"
        assert material.material_type == "tailored_resume"


@pytest.mark.django_db
class TestResumeTailorAgent:
    def test_tailors_and_records_execution(
        self, user, opportunity, active_resume, preferences
    ):
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content="# Tailored\n\nResume body",
            model_name="local-fallback",
            used_fallback=True,
        )
        agent = ResumeTailorAgent(provider=mock_provider)
        result = agent.tailor(user, opportunity)

        assert result["material"].content.startswith("# Tailored")
        assert result["material"].prompt_name == "resume_tailor"
        assert result["material"].metadata.get("pdf_available") is True
        assert AgentExecution.objects.filter(
            agent_name=RESUME_TAILOR_AGENT_NAME,
            status="completed",
        ).exists()
        mock_provider.generate.assert_called_once()

    def test_fails_without_active_resume(self, user, opportunity, preferences):
        agent = ResumeTailorAgent()
        with pytest.raises(NoActiveResumeError):
            agent.tailor(user, opportunity)
        assert AgentExecution.objects.filter(
            agent_name=RESUME_TAILOR_AGENT_NAME,
            status="failed",
        ).exists()


@pytest.mark.django_db
class TestCoverLetterAgent:
    def test_generates_cover_letter(
        self, user, opportunity, active_resume, preferences
    ):
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content="Dear Hiring Manager,\n\nI am excited to apply.",
            model_name="local-fallback",
            used_fallback=True,
        )
        agent = CoverLetterAgent(provider=mock_provider)
        result = agent.generate(user, opportunity)

        assert "Dear Hiring Manager" in result["material"].content
        assert result["material"].material_type == "cover_letter"
        assert AgentExecution.objects.filter(
            agent_name=COVER_LETTER_AGENT_NAME,
            status="completed",
        ).exists()

    def test_strips_placeholder_letterhead_from_generated_content(
        self, user, opportunity, active_resume, preferences
    ):
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content=(
                "[Your Name] [Your Email Address]\n"
                "[Date]\n"
                "Hiring Manager Odixcity Consulting India\n\n"
                "Dear Hiring Manager,\n\n"
                "I am excited to apply.\n\n"
                "Sincerely,\n[Your Name]\n"
            ),
            model_name="local-fallback",
            used_fallback=True,
        )
        agent = CoverLetterAgent(provider=mock_provider)
        result = agent.generate(user, opportunity)

        content = result["material"].content
        assert content.startswith("Dear Hiring Manager")
        assert "[Your Name]" not in content
        assert "[Date]" not in content
        assert "Sincerely" not in content


@pytest.mark.django_db
class TestTailorResumeAPI:
    def test_requires_auth(self, api_client, opportunity):
        url = reverse("opportunity-tailor-resume", args=[opportunity.id])
        response = api_client.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_tailors_resume(
        self, api_client, user, opportunity, active_resume, preferences
    ):
        api_client.force_authenticate(user=user)
        url = reverse("opportunity-tailor-resume", args=[opportunity.id])
        with patch.object(
            ApplicationMaterialsProvider,
            "generate",
            return_value=MaterialGenerationResult(
                content="# Tailored resume",
                model_name="local-fallback",
                used_fallback=True,
            ),
        ):
            response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["material"]["material_type"] == "tailored_resume"
        assert "agent_execution" in response.data

    def test_no_active_resume_returns_400(self, api_client, user, opportunity):
        api_client.force_authenticate(user=user)
        url = reverse("opportunity-tailor-resume", args=[opportunity.id])
        response = api_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "active resume" in response.data["detail"].lower()

    def test_ownership_isolation(
        self, api_client, user, opportunity, active_resume, preferences
    ):
        other = User.objects.create_user(
            email="other@example.com", password="pass12345"
        )
        api_client.force_authenticate(user=other)
        url = reverse("opportunity-tailor-resume", args=[opportunity.id])
        response = api_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCoverLetterAPI:
    def test_generates_cover_letter(
        self, api_client, user, opportunity, active_resume, preferences
    ):
        api_client.force_authenticate(user=user)
        url = reverse("opportunity-cover-letter", args=[opportunity.id])
        with patch(
            "apps.resumes.materials_provider.ApplicationMaterialsProvider.generate",
            return_value=MaterialGenerationResult(
                content="Dear Hiring Manager,",
                model_name="local-fallback",
                used_fallback=True,
            ),
        ):
            response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["material"]["material_type"] == "cover_letter"


@pytest.mark.django_db
class TestMaterialsAPI:
    def test_lists_materials_for_opportunity(
        self, api_client, user, opportunity, active_resume, preferences
    ):
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content="# Tailored",
            model_name="local-fallback",
        )
        ResumeTailorAgent(provider=mock_provider).tailor(user, opportunity)

        api_client.force_authenticate(user=user)
        url = reverse("opportunity-materials", args=[opportunity.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["materials"]) == 1
        assert response.data["materials"][0]["material_type"] == "tailored_resume"

    def test_resume_materials_list(
        self, api_client, user, opportunity, active_resume, preferences
    ):
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content="# Tailored",
            model_name="local-fallback",
        )
        ResumeTailorAgent(provider=mock_provider).tailor(user, opportunity)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("resume-materials"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["opportunity_title"] == "Senior Backend Engineer"


@pytest.mark.django_db
class TestMaterialContextUsesEvaluation:
    def test_prompt_includes_evaluation_and_research(
        self, user, opportunity, active_resume, preferences
    ):
        captured_prompt = {}

        def capture_generate(prompt_text, material_type):
            captured_prompt["text"] = prompt_text
            return MaterialGenerationResult(
                content="output",
                model_name="local-fallback",
            )

        agent = ResumeTailorAgent(
            provider=MagicMock(generate=capture_generate),
        )
        agent.tailor(user, opportunity)

        assert "Strong Python and Django alignment" in captured_prompt["text"]
        assert "Acme is growing fast" in captured_prompt["text"]
        assert "Years of experience (hard constraint)" in captured_prompt["text"]
        assert (
            "MUST NOT claim more than" in captured_prompt["text"]
            or "Do NOT state a specific year count" in captured_prompt["text"]
        )


@pytest.mark.django_db
class TestResumePdfExport:
    SAMPLE = json.dumps(
        {
            "professional_summary": "Backend engineer with Django experience.",
            "skills": [{"category": "Core:", "items": "Python, Django, PostgreSQL"}],
            "experience": [
                {
                    "title": "Engineer --- Acme Corp",
                    "dates": "2022 -- Present",
                    "description": "",
                    "bullets": [
                        "Built APIs at Acme Corp",
                        "Improved latency by 30%",
                    ],
                }
            ],
            "education": [],
        }
    )

    LEGACY_MARKDOWN = """# Jane Doe
Email: jane@example.com | Phone: 555-0100

## Professional Summary

Backend engineer with Django experience.
"""

    def test_generate_ats_resume_pdf_returns_bytes(self, monkeypatch):
        monkeypatch.setenv("CAREERPILOT_PDFLATEX_MOCK", "1")
        pdf_bytes = generate_ats_resume_pdf(self.SAMPLE)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")

    def test_legacy_markdown_pdf_fallback(self):
        pdf_bytes = generate_ats_resume_pdf(self.LEGACY_MARKDOWN)
        assert pdf_bytes.startswith(b"%PDF")

    def test_plain_text_strips_markdown_structure(self):
        text = plain_text_from_markdown(self.SAMPLE)
        assert "PROFESSIONAL SUMMARY" in text
        assert "Backend engineer" in text
        assert "#" not in text

    def test_pdf_download_api(self, api_client, user, opportunity, active_resume, preferences, monkeypatch):
        monkeypatch.setenv("CAREERPILOT_PDFLATEX_MOCK", "1")
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content=TestResumePdfExport.SAMPLE,
            model_name="local-fallback",
        )
        material = ResumeTailorAgent(provider=mock_provider).tailor(user, opportunity)[
            "material"
        ]

        api_client.force_authenticate(user=user)
        url = reverse("resume-material-pdf", args=[material.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

    COVER_LETTER_SAMPLE = """Dear Hiring Manager,

I am excited to apply for the Backend Engineer role at Acme Corp. My experience
building Django APIs aligns well with your team's needs.

Sincerely,
Jane Doe
"""

    def test_generate_cover_letter_pdf_returns_bytes(self):
        pdf_bytes = generate_cover_letter_pdf(self.COVER_LETTER_SAMPLE)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")

    def test_pdf_download_cover_letter(
        self, api_client, user, opportunity, active_resume, preferences, monkeypatch
    ):
        monkeypatch.setenv("CAREERPILOT_PDFLATEX_MOCK", "1")
        mock_provider = MagicMock()
        mock_provider.generate.return_value = MaterialGenerationResult(
            content=self.COVER_LETTER_SAMPLE,
            model_name="local-fallback",
        )
        material = CoverLetterAgent(provider=mock_provider).generate(user, opportunity)[
            "material"
        ]

        api_client.force_authenticate(user=user)
        url = reverse("resume-material-pdf", args=[material.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
        assert 'filename="cover-letter-' in response["Content-Disposition"]

        material.refresh_from_db()
        assert material.metadata.get("pdf_engine") in {"latex", "fpdf2"}
