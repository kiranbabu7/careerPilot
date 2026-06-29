import json
import os
from unittest.mock import patch

import pytest

pytest_plugins = [
    "apps.resumes.tests.test_phase2",
    "apps.jobs.tests.test_phase6",
]

from apps.resumes.latex_export import (
    compile_latex_to_pdf,
    escape_latex,
    is_pdflatex_available,
    normalize_cover_letter_content,
    parse_cover_letter_markdown,
    render_cover_letter_latex_document,
    render_latex_document,
)
from apps.resumes.pdf_export import (
    generate_ats_resume_pdf,
    generate_ats_resume_pdf_with_engine,
    generate_cover_letter_pdf_with_engine,
    plain_text_from_markdown,
)
from apps.resumes.resume_content import (
    TailoredResumeContent,
    ExperienceEntry,
    SkillRow,
    EducationEntry,
    ResumeContact,
    parse_tailored_resume_content,
)


SAMPLE_JSON = {
    "professional_summary": "Backend engineer with Django experience.",
    "skills": [
        {"category": "Languages:", "items": "Python, Django, PostgreSQL"},
    ],
    "experience": [
        {
            "title": "Software Engineer --- Acme Corp",
            "dates": "2022 -- Present",
            "description": "Backend development on SaaS platform.",
            "bullets": [
                "Built REST APIs with Django",
                "Improved latency by 30%",
            ],
        }
    ],
    "education": [
        {"title": "B.S. Computer Science --- State University", "dates": "2018 -- 2022"}
    ],
}


@pytest.fixture
def sample_content() -> str:
    return json.dumps(SAMPLE_JSON)


class TestResumeContentParsing:
    def test_parse_json_content(self, sample_content):
        parsed = parse_tailored_resume_content(sample_content)
        assert parsed is not None
        assert parsed.professional_summary.startswith("Backend engineer")
        assert len(parsed.experience) == 1
        assert parsed.experience[0].bullets[0].startswith("Built REST")

    def test_legacy_markdown_returns_none(self):
        assert parse_tailored_resume_content("# Jane Doe\n\nSummary") is None


class TestLatexExport:
    def test_escape_latex_special_chars(self):
        assert escape_latex("100% & $") == r"100\% \& \$"

    def test_render_document_uses_placeholders_not_hardcoded_name(self):
        content = TailoredResumeContent(
            professional_summary="Summary text",
            skills=[SkillRow("Tools:", "Git")],
            experience=[
                ExperienceEntry(
                    title="Engineer --- Co",
                    dates="2024 -- Present",
                    bullets=["Did work"],
                )
            ],
            education=[EducationEntry("BS --- School", "2020 -- 2024")],
        )
        contact = ResumeContact(
            full_name="Jane Doe",
            email="jane@example.com",
            phone="555-0100",
            location="Remote",
        )
        latex = render_latex_document(content, contact)
        assert "Jane Doe" in latex
        assert "Kiran" not in latex
        assert r"\cvsection{PROFESSIONAL SUMMARY}" in latex
        assert r"\skillrow{Tools:}{Git}" in latex

    def test_mock_pdflatex_compilation(self, sample_content, monkeypatch):
        monkeypatch.setenv("CAREERPILOT_PDFLATEX_MOCK", "1")
        assert is_pdflatex_available() is True
        pdf_bytes = compile_latex_to_pdf("\\documentclass{article}\\begin{document}Hi\\end{document}")
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_pdf_with_mock_latex(self, sample_content, user, monkeypatch):
        monkeypatch.setenv("CAREERPILOT_PDFLATEX_MOCK", "1")
        pdf_bytes, engine = generate_ats_resume_pdf_with_engine(
            sample_content,
            user=user,
            resume_text="Jane Doe\njane@example.com",
        )
        assert engine == "latex"
        assert pdf_bytes.startswith(b"%PDF")

    def test_fpdf_fallback_when_latex_fails(self, sample_content, user, monkeypatch):
        monkeypatch.delenv("CAREERPILOT_PDFLATEX_MOCK", raising=False)

        def boom(*args, **kwargs):
            raise RuntimeError("pdflatex unavailable")

        monkeypatch.setattr(
            "apps.resumes.latex_export.compile_latex_to_pdf",
            boom,
        )
        pdf_bytes, engine = generate_ats_resume_pdf_with_engine(
            sample_content,
            user=user,
        )
        assert engine == "fpdf2"
        assert pdf_bytes.startswith(b"%PDF")

    def test_legacy_markdown_still_renders_fpdf(self):
        markdown = "# Jane Doe\n\n## Professional Summary\n\nBackend engineer."
        pdf_bytes = generate_ats_resume_pdf(markdown)
        assert pdf_bytes.startswith(b"%PDF")

    def test_plain_text_from_json(self, sample_content):
        text = plain_text_from_markdown(sample_content)
        assert "PROFESSIONAL SUMMARY" in text
        assert "Backend engineer" in text
        assert "#" not in text


@pytest.mark.django_db
def test_pdf_download_api_uses_latex_engine(api_client, user, opportunity, active_resume, preferences):
    from django.urls import reverse
    from rest_framework import status
    from unittest.mock import MagicMock

    from apps.agents.resume_tailoring import ResumeTailorAgent
    from apps.resumes.materials_provider import MaterialGenerationResult

    mock_provider = MagicMock()
    mock_provider.generate.return_value = MaterialGenerationResult(
        content=json.dumps(SAMPLE_JSON),
        model_name="local-fallback",
    )

    with patch.dict(os.environ, {"CAREERPILOT_PDFLATEX_MOCK": "1"}):
        material = ResumeTailorAgent(provider=mock_provider).tailor(user, opportunity)[
            "material"
        ]

        api_client.force_authenticate(user=user)
        url = reverse("resume-material-pdf", args=[material.id])
        response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

    material.refresh_from_db()
    assert material.metadata.get("pdf_engine") in {"latex", "fpdf2"}


COVER_LETTER_SAMPLE = """Dear Hiring Manager,

I am excited to apply for the **Backend Engineer** role at Acme Corp.

- Built REST APIs with Django
- Improved latency by 30%

Sincerely,
Jane Doe
"""


COVER_LETTER_WITH_PLACEHOLDERS = """[Your Name] [Your Address] [Your Phone Number] [Your Email Address]
[Date]
Hiring Manager Odixcity Consulting [Company Address - if known, otherwise omit] India

Dear Hiring Manager,

I am excited to apply for the **Backend Engineer** role at Acme Corp.

Sincerely,
[Your Name]
"""


class TestCoverLetterLatexExport:
    def test_normalize_cover_letter_strips_letterhead_and_placeholders(self):
        normalized = normalize_cover_letter_content(
            COVER_LETTER_WITH_PLACEHOLDERS,
            company="Odixcity Consulting",
        )
        assert normalized.startswith("Dear Hiring Manager")
        assert "[Your Name]" not in normalized
        assert "[Date]" not in normalized
        assert "Sincerely" not in normalized
        assert "Odixcity Consulting" not in normalized.split("Dear Hiring Manager,")[0]

    def test_render_cover_letter_omits_placeholder_body_lines(self):
        contact = ResumeContact(
            full_name="Jane Doe",
            email="jane@example.com",
            phone="555-0100",
            location="Remote",
        )
        latex = render_cover_letter_latex_document(
            COVER_LETTER_WITH_PLACEHOLDERS,
            contact=contact,
            company="Odixcity Consulting",
            job_location="India",
        )
        assert "Jane Doe" in latex
        assert "[Your Name]" not in latex
        assert "[Date]" not in latex
        assert "Odixcity Consulting" in latex
        assert "India" in latex

    def test_parse_cover_letter_markdown(self):
        parsed = parse_cover_letter_markdown(COVER_LETTER_SAMPLE)
        assert parsed.salutation == "Dear Hiring Manager,"
        assert len(parsed.blocks) == 2
        assert parsed.blocks[0].type == "paragraph"
        assert parsed.blocks[1].type == "bullets"
        assert parsed.blocks[1].items[0].startswith("Built REST")
        assert parsed.closing.lower().startswith("sincerely")
        assert parsed.signature == "Jane Doe"

    def test_render_cover_letter_uses_placeholders(self):
        contact = ResumeContact(
            full_name="Jane Doe",
            email="jane@example.com",
            phone="555-0100",
            location="Remote",
        )
        latex = render_cover_letter_latex_document(
            COVER_LETTER_SAMPLE,
            contact=contact,
            company="Acme Corp",
            job_location="San Francisco, CA",
            letter_date=__import__("datetime").date(2026, 6, 28),
        )
        assert "Jane Doe" in latex
        assert "Richard Williams" not in latex
        assert "Acme Corp" in latex
        assert "San Francisco, CA" in latex
        assert "June 28, 2026" in latex
        assert r"\textbf{Backend Engineer}" in latex
        assert r"\begin{itemize}" in latex

    def test_escape_latex_in_cover_letter_body(self):
        content = "Dear Hiring Manager,\n\nWe improved sales by 20%.\n\nSincerely,\nJane"
        parsed = parse_cover_letter_markdown(content)
        contact = ResumeContact(full_name="Jane Doe")
        latex = render_cover_letter_latex_document(
            content,
            contact=contact,
            company="R&D Co",
        )
        assert r"20\%" in latex
        assert r"R\&D Co" in latex

    def test_generate_cover_letter_pdf_with_mock_latex(self, user, monkeypatch):
        monkeypatch.setenv("CAREERPILOT_PDFLATEX_MOCK", "1")
        pdf_bytes, engine = generate_cover_letter_pdf_with_engine(
            COVER_LETTER_SAMPLE,
            user=user,
            resume_text="Jane Doe\njane@example.com",
            company="Acme Corp",
            job_location="Remote",
        )
        assert engine == "latex"
        assert pdf_bytes.startswith(b"%PDF")

    def test_cover_letter_fpdf_fallback_when_latex_fails(self, user, monkeypatch):
        monkeypatch.delenv("CAREERPILOT_PDFLATEX_MOCK", raising=False)

        def boom(*args, **kwargs):
            raise RuntimeError("pdflatex unavailable")

        monkeypatch.setattr(
            "apps.resumes.latex_export.compile_latex_to_pdf",
            boom,
        )
        pdf_bytes, engine = generate_cover_letter_pdf_with_engine(
            COVER_LETTER_SAMPLE,
            user=user,
        )
        assert engine == "fpdf2"
        assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.django_db
def test_pdf_download_cover_letter_api_uses_latex_engine(
    api_client, user, opportunity, active_resume, preferences
):
    from django.urls import reverse
    from rest_framework import status
    from unittest.mock import MagicMock

    from apps.agents.cover_letter import CoverLetterAgent
    from apps.resumes.materials_provider import MaterialGenerationResult

    mock_provider = MagicMock()
    mock_provider.generate.return_value = MaterialGenerationResult(
        content=COVER_LETTER_SAMPLE,
        model_name="local-fallback",
    )

    with patch.dict(os.environ, {"CAREERPILOT_PDFLATEX_MOCK": "1"}):
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
