"""LaTeX resume and cover letter rendering and pdfLaTeX compilation."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from apps.resumes.resume_content import (
    ResumeContact,
    TailoredResumeContent,
    extract_contact_from_sources,
    parse_tailored_resume_content,
)

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "resume_base.tex"
COVER_LETTER_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "cover_letter_base.tex"
)

_SALUTATION_RE = re.compile(r"^dear\s+", re.IGNORECASE)
_CLOSING_RE = re.compile(
    r"^(sincerely|best regards|kind regards|regards|thank you|warm regards|yours truly),?\s*$",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"^[-*•]\s+(.+)$")

_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    if not text:
        return ""
    escaped = []
    for char in text:
        escaped.append(_LATEX_SPECIAL.get(char, char))
    return "".join(escaped)


def is_pdflatex_available() -> bool:
    if os.environ.get("CAREERPILOT_PDFLATEX_MOCK") == "1":
        return True
    return shutil.which("pdflatex") is not None


def render_latex_document(
    content: TailoredResumeContent,
    contact: ResumeContact,
) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{FULL_NAME}}": escape_latex(contact.full_name),
        "{{CONTACT_LINE}}": _render_contact_line(contact),
        "{{PROFESSIONAL_SUMMARY}}": escape_latex(content.professional_summary),
        "{{TECHNICAL_SKILLS}}": _render_skills(content),
        "{{WORK_EXPERIENCE}}": _render_experience(content),
        "{{EDUCATION}}": _render_education(content),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def compile_latex_to_pdf(
    latex_source: str,
    *,
    timeout: int = 60,
    job_name: str = "document",
) -> bytes:
    if os.environ.get("CAREERPILOT_PDFLATEX_MOCK") == "1":
        return _mock_pdf_bytes()

    if not shutil.which("pdflatex"):
        raise RuntimeError("pdflatex not available")

    tex_file = f"{job_name}.tex"
    pdf_file = f"{job_name}.pdf"
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / tex_file
        tex_path.write_text(latex_source, encoding="utf-8")
        command = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_file,
        ]
        for _ in range(2):
            result = subprocess.run(
                command,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "pdflatex failed: "
                    f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
                )
        pdf_path = Path(tmpdir) / pdf_file
        if not pdf_path.exists():
            raise RuntimeError(f"pdflatex did not produce {pdf_file}")
        return pdf_path.read_bytes()


def generate_latex_resume_pdf(
    content: str,
    *,
    user=None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
) -> bytes:
    structured = parse_tailored_resume_content(content)
    if structured is None:
        raise ValueError("content is not structured JSON")

    contact = extract_contact_from_sources(
        user=user,
        resume_text=resume_text,
        target_locations=target_locations,
    )
    latex_source = render_latex_document(structured, contact)
    return compile_latex_to_pdf(latex_source, job_name="resume")


@dataclass
class CoverLetterBlock:
    type: str
    text: str = ""
    items: list[str] = field(default_factory=list)


@dataclass
class CoverLetterParsed:
    salutation: str = ""
    blocks: list[CoverLetterBlock] = field(default_factory=list)
    closing: str = "Sincerely,"
    signature: str = ""


def parse_cover_letter_markdown(content: str) -> CoverLetterParsed:
    """Split cover letter markdown into salutation, body blocks, closing, signature."""
    lines = [line.rstrip() for line in content.strip().splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    salutation = ""
    if lines and _SALUTATION_RE.match(lines[0].strip()):
        salutation = lines[0].strip()
        lines = lines[1:]

    closing = "Sincerely,"
    signature = ""
    while lines:
        stripped = lines[-1].strip()
        if not stripped:
            lines.pop()
            continue
        if not signature and _looks_like_signature(stripped, salutation):
            signature = _clean_inline(stripped)
            lines.pop()
            continue
        if _CLOSING_RE.match(stripped):
            closing = _clean_inline(stripped)
            if not closing.endswith(","):
                closing = f"{closing},"
            lines.pop()
            continue
        break

    blocks = _parse_body_blocks(lines)
    return CoverLetterParsed(
        salutation=salutation,
        blocks=blocks,
        closing=closing,
        signature=signature,
    )


def render_cover_letter_latex_document(
    content: str,
    *,
    contact: ResumeContact,
    company: str = "",
    job_location: str = "",
    letter_date: date | None = None,
) -> str:
    template = COVER_LETTER_TEMPLATE_PATH.read_text(encoding="utf-8")
    parsed = parse_cover_letter_markdown(content)
    signature = parsed.signature or contact.full_name
    replacements = {
        "{{FULL_NAME}}": escape_latex(contact.full_name),
        "{{CONTACT_LINE}}": _render_cover_letter_contact_line(contact),
        "{{LETTER_DATE}}": escape_latex(_format_letter_date(letter_date)),
        "{{RECIPIENT_BLOCK}}": _render_recipient_block(company, job_location),
        "{{LETTER_BODY}}": _render_cover_letter_body(parsed),
        "{{CLOSING}}": escape_latex(parsed.closing),
        "{{SIGNATURE_NAME}}": escape_latex(signature),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def generate_latex_cover_letter_pdf(
    content: str,
    *,
    user=None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
    company: str = "",
    job_location: str = "",
    letter_date: date | None = None,
) -> bytes:
    contact = extract_contact_from_sources(
        user=user,
        resume_text=resume_text,
        target_locations=target_locations,
    )
    latex_source = render_cover_letter_latex_document(
        content,
        contact=contact,
        company=company,
        job_location=job_location,
        letter_date=letter_date,
    )
    return compile_latex_to_pdf(latex_source, job_name="cover_letter")


def _render_contact_line(contact: ResumeContact) -> str:
    parts: list[str] = []
    if contact.phone:
        parts.append(escape_latex(contact.phone))
    if contact.email:
        email = escape_latex(contact.email)
        parts.append(rf"\href{{mailto:{email}}}{{{email}}}")
    if contact.location:
        parts.append(escape_latex(contact.location))
    if contact.github_url and contact.github_label:
        url = contact.github_url
        label = escape_latex(contact.github_label)
        parts.append(rf"\href{{{url}}}{{{label}}}")
    if not parts:
        return escape_latex("Contact details available upon request")
    return "\n    ~\\textbullet~\n    ".join(parts)


def _render_skills(content: TailoredResumeContent) -> str:
    rows = []
    for skill in content.skills:
        if not skill.category and not skill.items:
            continue
        rows.append(
            rf"\skillrow{{{escape_latex(skill.category)}}}{{{escape_latex(skill.items)}}}"
        )
    return "\n".join(rows)


def _render_experience(content: TailoredResumeContent) -> str:
    blocks: list[str] = []
    for job in content.experience:
        if not job.title:
            continue
        blocks.append(
            rf"\jobheading{{{escape_latex(job.title)}}}{{{escape_latex(job.dates)}}}"
        )
        if job.description:
            blocks.append(rf"\roledesc{{{escape_latex(job.description)}}}")
        if job.bullets:
            items = "\n  ".join(
                rf"\item {escape_latex(bullet)}" for bullet in job.bullets
            )
            blocks.append(rf"\begin{{cvlist}}{items}\end{{cvlist}}")
    return "\n\n".join(blocks)


def _render_education(content: TailoredResumeContent) -> str:
    blocks: list[str] = []
    for edu in content.education:
        if not edu.title:
            continue
        blocks.append(
            rf"\jobheading{{{escape_latex(edu.title)}}}{{{escape_latex(edu.dates)}}}"
        )
    return "\n".join(blocks)


def _mock_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<<>>endobj\n"
        b"trailer<< /Root 1 0 R /Size 1 >>\n"
        b"startxref\n9\n%%EOF\n"
    )


def _render_cover_letter_contact_line(contact: ResumeContact) -> str:
    parts: list[str] = []
    if contact.location:
        parts.append(escape_latex(contact.location))
    if contact.email:
        email = escape_latex(contact.email)
        parts.append(rf"\href{{mailto:{email}}}{{{email}}}")
    if contact.phone:
        parts.append(escape_latex(contact.phone))
    if contact.github_url and contact.github_label:
        url = contact.github_url
        label = escape_latex(contact.github_label)
        parts.append(rf"\href{{{url}}}{{{label}}}")
    if not parts:
        return escape_latex("Contact details available upon request")
    return r" \textbullet{} ".join(parts)


def _format_letter_date(letter_date: date | None) -> str:
    current = letter_date or date.today()
    return current.strftime("%B %d, %Y")


def _render_recipient_block(company: str, job_location: str) -> str:
    lines: list[str] = [escape_latex("Hiring Manager")]
    if company.strip():
        lines.append(escape_latex(company.strip()))
    if job_location.strip():
        lines.append(escape_latex(job_location.strip()))
    return r" \\".join(lines)


def _render_cover_letter_body(parsed: CoverLetterParsed) -> str:
    parts: list[str] = []
    if parsed.salutation:
        parts.append(f"{_render_inline_markdown(parsed.salutation)}\n\n\\vspace{{1em}}\n")

    for block in parsed.blocks:
        if block.type == "paragraph" and block.text:
            parts.append(
                f"{_render_inline_markdown(block.text)}\n\n\\vspace{{1em}}\n"
            )
        elif block.type == "bullets" and block.items:
            items = "\n    ".join(
                rf"\item {_render_inline_markdown(item)}" for item in block.items
            )
            parts.append(
                rf"\begin{{itemize}}"
                "\n    "
                f"{items}"
                "\n"
                rf"\end{{itemize}}"
                "\n\n\\vspace{1em}\n"
            )
    return "".join(parts)


def _parse_body_blocks(lines: list[str]) -> list[CoverLetterBlock]:
    blocks: list[CoverLetterBlock] = []
    paragraph_lines: list[str] = []
    bullet_items: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines).strip()
            if text:
                blocks.append(CoverLetterBlock(type="paragraph", text=text))
            paragraph_lines = []

    def flush_bullets() -> None:
        nonlocal bullet_items
        if bullet_items:
            blocks.append(CoverLetterBlock(type="bullets", items=bullet_items))
            bullet_items = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_bullets()
            continue

        bullet_match = _BULLET_RE.match(stripped)
        if bullet_match:
            flush_paragraph()
            bullet_items.append(bullet_match.group(1).strip())
            continue

        flush_bullets()
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_bullets()
    return blocks


def _render_inline_markdown(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in re.finditer(r"\*\*(.+?)\*\*", text):
        if match.start() > last:
            parts.append(escape_latex(text[last : match.start()]))
        parts.append(rf"\textbf{{{escape_latex(match.group(1))}}}")
        last = match.end()
    if last < len(text):
        parts.append(escape_latex(text[last:]))
    return "".join(parts) if parts else escape_latex(text)


def _clean_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _looks_like_signature(line: str, salutation: str) -> bool:
    cleaned = _clean_inline(line)
    if not cleaned:
        return False
    if _SALUTATION_RE.match(cleaned) or _CLOSING_RE.match(cleaned):
        return False
    if len(cleaned.split()) > 6:
        return False
    if salutation and cleaned.lower() in salutation.lower():
        return False
    return True
