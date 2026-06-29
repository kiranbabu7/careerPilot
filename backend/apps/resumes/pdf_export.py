"""Generate ATS-friendly single-column PDF resumes from tailored content."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from apps.resumes.latex_export import (
    generate_latex_cover_letter_pdf,
    generate_latex_resume_pdf,
    is_pdflatex_available,
)
from apps.resumes.resume_content import (
    content_to_preview_text,
    iter_structured_smoke_errors,
    parse_tailored_resume_content,
)

logger = logging.getLogger(__name__)

# Map common resume headings to standard ATS section titles.
_STANDARD_HEADINGS = {
    "professional summary": "PROFESSIONAL SUMMARY",
    "summary": "PROFESSIONAL SUMMARY",
    "profile": "PROFESSIONAL SUMMARY",
    "experience": "PROFESSIONAL EXPERIENCE",
    "work experience": "PROFESSIONAL EXPERIENCE",
    "professional experience": "PROFESSIONAL EXPERIENCE",
    "employment history": "PROFESSIONAL EXPERIENCE",
    "education": "EDUCATION",
    "skills": "SKILLS",
    "technical skills": "SKILLS",
    "core competencies": "SKILLS",
    "certifications": "CERTIFICATIONS",
    "projects": "PROJECTS",
    "contact": "CONTACT",
}


def generate_cover_letter_pdf(
    content: str,
    *,
    user=None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
    company: str = "",
    job_location: str = "",
) -> bytes:
    """Render cover letter markdown as a PDF letter."""
    pdf_bytes, _ = generate_cover_letter_pdf_with_engine(
        content,
        user=user,
        resume_text=resume_text,
        target_locations=target_locations,
        company=company,
        job_location=job_location,
    )
    return pdf_bytes


def generate_cover_letter_pdf_with_engine(
    content: str,
    *,
    user=None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
    company: str = "",
    job_location: str = "",
) -> tuple[bytes, str]:
    """Return PDF bytes and engine name (`latex` or `fpdf2`)."""
    if is_pdflatex_available():
        try:
            pdf_bytes = generate_latex_cover_letter_pdf(
                content.strip(),
                user=user,
                resume_text=resume_text,
                target_locations=target_locations,
                company=company,
                job_location=job_location,
            )
            return pdf_bytes, "latex"
        except Exception:
            logger.exception("LaTeX cover letter PDF failed; falling back to fpdf2")
    return _generate_fpdf_from_markdown(content.strip()), "fpdf2"


def generate_ats_resume_pdf(
    content: str,
    *,
    user=None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
) -> bytes:
    """Render tailored resume content as an ATS-friendly PDF."""
    structured = parse_tailored_resume_content(content)
    if structured is not None:
        try:
            return generate_latex_resume_pdf(
                content,
                user=user,
                resume_text=resume_text,
                target_locations=target_locations,
            )
        except Exception:
            logger.exception("LaTeX PDF generation failed; falling back to fpdf2")
            preview = content_to_preview_text(content)
            return _generate_fpdf_from_markdown(preview)

    return _generate_fpdf_from_markdown(content)


def generate_ats_resume_pdf_with_engine(
    content: str,
    *,
    user=None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
) -> tuple[bytes, str]:
    """Return PDF bytes and engine name (`latex` or `fpdf2`)."""
    structured = parse_tailored_resume_content(content)
    if structured is not None:
        try:
            pdf_bytes = generate_latex_resume_pdf(
                content,
                user=user,
                resume_text=resume_text,
                target_locations=target_locations,
            )
            return pdf_bytes, "latex"
        except Exception:
            logger.exception("LaTeX PDF generation failed; falling back to fpdf2")
    preview = content_to_preview_text(content) if structured else content
    return _generate_fpdf_from_markdown(preview), "fpdf2"


def _generate_fpdf_from_markdown(content: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    blocks = _parse_blocks(content)
    for block in blocks:
        _render_block(pdf, block)

    raw = pdf.output()
    return bytes(raw)


def _parse_blocks(content: str) -> list[dict]:
    """Split markdown into ordered blocks for linear PDF rendering."""
    blocks: list[dict] = []
    current_section: dict | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _is_table_line(stripped):
            continue
        if stripped.startswith("---"):
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title = _clean_inline(heading_match.group(2))
            if level == 1 and not blocks:
                blocks.append({"type": "name", "text": title})
                continue
            section_title = _normalize_section(title)
            current_section = {"type": "section", "title": section_title, "lines": []}
            blocks.append(current_section)
            continue

        bullet_match = re.match(r"^[-*•]\s+(.+)$", stripped)
        if bullet_match:
            text = _clean_inline(bullet_match.group(1))
            bullet_line = f"- {text}"
            if current_section and current_section["type"] == "section":
                current_section["lines"].append(bullet_line)
            else:
                blocks.append({"type": "paragraph", "text": bullet_line})
            continue

        text = _clean_inline(stripped)
        if current_section and current_section["type"] == "section":
            current_section["lines"].append(text)
        else:
            blocks.append({"type": "paragraph", "text": text})

    return blocks


def _render_block(pdf, block: dict) -> None:
    block_type = block["type"]
    if block_type == "name":
        _write_line(pdf, block["text"], height=8, bold=True, size=16)
        pdf.ln(2)
        return

    if block_type == "section":
        pdf.ln(3)
        _write_line(pdf, block["title"], height=7, bold=True, size=12)
        pdf.ln(1)
        for line in block.get("lines", []):
            _write_line(pdf, line, height=5.5, size=11)
        return

    if block_type == "paragraph":
        _write_line(pdf, block["text"], height=5.5, size=11)
        pdf.ln(1)


def _write_line(
    pdf,
    text: str,
    *,
    height: float = 5.5,
    bold: bool = False,
    size: int = 11,
) -> None:
    style = "B" if bold else ""
    pdf.set_font("Helvetica", style, size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        pdf.epw,
        height,
        _pdf_safe(text),
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _pdf_safe(text: str) -> str:
    """Keep PDF body text compatible with core Helvetica encoding."""
    return text.replace("\u2022", "-").encode("latin-1", "replace").decode("latin-1")


def _normalize_section(title: str) -> str:
    key = title.strip().lower()
    return _STANDARD_HEADINGS.get(key, title.strip().upper())


def _clean_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _is_table_line(line: str) -> bool:
    if "|" in line and line.count("|") >= 2:
        return True
    return bool(re.match(r"^[\|\s:-]+$", line))


def plain_text_from_markdown(content: str) -> str:
    """Convert resume content to plain single-column text (ATS preview)."""
    structured = parse_tailored_resume_content(content)
    if structured is not None:
        return content_to_preview_text(content)

    lines: list[str] = []
    for block in _parse_blocks(content):
        if block["type"] == "name":
            lines.append(block["text"])
            lines.append("")
        elif block["type"] == "section":
            lines.append(block["title"])
            lines.extend(block.get("lines", []))
            lines.append("")
        elif block["type"] == "paragraph":
            lines.append(block["text"])
    return "\n".join(lines).strip()


def iter_pdf_smoke_errors(content: str) -> Iterable[str]:
    """Return validation issues; empty when content is PDF-safe."""
    if not content.strip():
        yield "empty content"
        return

    structured = parse_tailored_resume_content(content)
    if structured is not None:
        yield from iter_structured_smoke_errors(content)
        return

    for line in content.splitlines():
        if _is_table_line(line.strip()):
            yield "table detected"


def pdf_generation_capabilities() -> dict[str, bool]:
    return {
        "pdflatex_available": is_pdflatex_available(),
    }
