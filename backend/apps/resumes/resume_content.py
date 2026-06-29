"""Parse and validate structured tailored resume content."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable


@dataclass
class SkillRow:
    category: str
    items: str


@dataclass
class ExperienceEntry:
    title: str
    dates: str
    description: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class EducationEntry:
    title: str
    dates: str


@dataclass
class TailoredResumeContent:
    professional_summary: str
    skills: list[SkillRow] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)


@dataclass
class ResumeContact:
    full_name: str
    phone: str = ""
    email: str = ""
    location: str = ""
    github_url: str = ""
    github_label: str = ""


def strip_content_fences(content: str) -> str:
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if fence_match:
        return fence_match.group(1).strip()
    return content.strip()


def parse_tailored_resume_content(content: str) -> TailoredResumeContent | None:
    """Return structured resume data when content is JSON; None for legacy markdown."""
    text = strip_content_fences(content)
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return _payload_to_content(payload)


def _payload_to_content(payload: dict[str, Any]) -> TailoredResumeContent:
    skills = [
        SkillRow(
            category=str(row.get("category", "")).strip(),
            items=str(row.get("items", "")).strip(),
        )
        for row in payload.get("skills") or []
        if isinstance(row, dict)
    ]
    experience = [
        ExperienceEntry(
            title=str(row.get("title", "")).strip(),
            dates=str(row.get("dates", "")).strip(),
            description=str(row.get("description", "")).strip(),
            bullets=[
                str(item).strip()
                for item in (row.get("bullets") or [])
                if str(item).strip()
            ],
        )
        for row in payload.get("experience") or []
        if isinstance(row, dict)
    ]
    education = [
        EducationEntry(
            title=str(row.get("title", "")).strip(),
            dates=str(row.get("dates", "")).strip(),
        )
        for row in payload.get("education") or []
        if isinstance(row, dict)
    ]
    return TailoredResumeContent(
        professional_summary=str(payload.get("professional_summary", "")).strip(),
        skills=skills,
        experience=experience,
        education=education,
    )


def content_to_preview_text(content: str) -> str:
    """Human-readable preview for UI display."""
    structured = parse_tailored_resume_content(content)
    if structured is None:
        return content
    lines: list[str] = []
    if structured.professional_summary:
        lines.extend(["PROFESSIONAL SUMMARY", structured.professional_summary, ""])
    if structured.skills:
        lines.append("TECHNICAL SKILLS")
        for skill in structured.skills:
            lines.append(f"{skill.category} {skill.items}".strip())
        lines.append("")
    if structured.experience:
        lines.append("WORK EXPERIENCE")
        for job in structured.experience:
            lines.append(f"{job.title} | {job.dates}")
            if job.description:
                lines.append(job.description)
            for bullet in job.bullets:
                lines.append(f"- {bullet}")
            lines.append("")
    if structured.education:
        lines.append("EDUCATION")
        for edu in structured.education:
            lines.append(f"{edu.title} | {edu.dates}")
    return "\n".join(lines).strip()


def iter_structured_smoke_errors(content: str) -> Iterable[str]:
    structured = parse_tailored_resume_content(content)
    if structured is None:
        yield "content is not structured JSON"
        return
    if not structured.professional_summary.strip():
        yield "missing professional_summary"
    if not structured.experience:
        yield "missing experience entries"


def extract_contact_from_sources(
    *,
    user,
    resume_text: str = "",
    target_locations: list[str] | None = None,
) -> ResumeContact:
    """Build contact block from user profile and source resume text."""
    resume_text = resume_text or ""
    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    full_name = f"{first_name} {last_name}".strip()

    if not full_name:
        heading = _first_non_empty_line(resume_text)
        if heading and not _looks_like_contact_line(heading):
            full_name = heading

    if not full_name:
        full_name = "Candidate"

    email = getattr(user, "email", "") or ""
    if not email:
        email = _first_match(
            resume_text,
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        )

    phone = _first_match(
        resume_text,
        r"(?:\+?\d[\d\s().-]{7,}\d)",
    )
    location = ""
    if target_locations:
        location = target_locations[0]
    if not location:
        location = _first_match(
            resume_text,
            r"(?:Remote|[A-Z][a-zA-Z\s]+,\s*[A-Z]{2,}(?:,\s*[A-Za-z\s]+)?)",
        )

    github_url = ""
    github_label = ""
    github_match = re.search(
        r"(https?://github\.com/[\w-]+|github\.com/[\w-]+)",
        resume_text,
        re.IGNORECASE,
    )
    if github_match:
        raw = github_match.group(1)
        github_url = raw if raw.startswith("http") else f"https://{raw}"
        github_label = raw.replace("https://", "").replace("http://", "")

    return ResumeContact(
        full_name=full_name,
        phone=phone.strip(),
        email=email.strip(),
        location=location.strip(),
        github_url=github_url.strip(),
        github_label=github_label.strip(),
    )


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _looks_like_contact_line(line: str) -> bool:
    lowered = line.lower()
    return "@" in line or "http" in lowered or re.search(r"\d{3}", line) is not None


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(0).strip() if match else ""


_MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_EXPERIENCE_SECTION_HEADER = re.compile(
    r"^\s*(?:work\s+)?experience|employment(?:\s+history)?|professional\s+experience|career\s+history",
    re.IGNORECASE,
)
_NEXT_SECTION_HEADER = re.compile(
    r"^\s*(?:education|skills|technical\s+skills|projects|certifications|awards|summary|objective|references)",
    re.IGNORECASE,
)
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_RANGE_SEPARATOR = r"(?:--|–|—|-|to|through)"
_PRESENT = r"(?:Present|Current|Now)"
_END_TOKEN = rf"(?:{_PRESENT}|(?:{_MONTH}\s+)?\d{{4}})"
_DATE_RANGE_PATTERN = re.compile(
    rf"(?:(?P<month>{_MONTH})\s+(?P<start_year>\d{{4}})|(?P<year_only>\d{{4}}))\s*"
    rf"{_RANGE_SEPARATOR}\s*(?P<end>{_END_TOKEN})",
    re.IGNORECASE,
)


def compute_years_of_experience(
    resume_text: str,
    *,
    reference_date: date | None = None,
) -> int | None:
    """Return total professional years derived from employment date ranges in resume text."""
    if not resume_text or not resume_text.strip():
        return None

    reference_date = reference_date or date.today()
    ranges = _extract_employment_date_ranges(resume_text, reference_date)
    if not ranges:
        return None

    merged = _merge_date_ranges(ranges)
    total_months = sum(_months_between(start, end) for start, end in merged)
    if total_months <= 0:
        return None
    return total_months // 12


def format_years_of_experience_constraint(
    years: int | None,
    *,
    reference_date: date | None = None,
) -> str:
    """Prompt-ready constraint text for resume tailoring."""
    if years is None:
        return (
            "Could not be computed from employment dates in the source resume. "
            "Do NOT state a specific year count in the professional summary unless "
            "it appears verbatim in the source resume."
        )
    reference_date = reference_date or date.today()
    return (
        f"{years} years total (computed from employment dates in the source resume "
        f"as of {reference_date.strftime('%b %Y')}). "
        f"You MUST NOT claim more than {years} years of professional experience. "
        f"Use wording like '{years}+ years' only when {years} is an exact floor from "
        f"those employment dates."
    )


def _extract_experience_section(text: str) -> str:
    lines = text.splitlines()
    in_experience = False
    experience_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _EXPERIENCE_SECTION_HEADER.match(stripped):
            in_experience = True
            continue
        if in_experience and _NEXT_SECTION_HEADER.match(stripped):
            break
        if in_experience:
            experience_lines.append(line)
    if experience_lines:
        return "\n".join(experience_lines)
    return text


def _extract_employment_date_ranges(
    resume_text: str,
    reference_date: date,
) -> list[tuple[date, date]]:
    search_text = _extract_experience_section(resume_text)
    ranges: list[tuple[date, date]] = []
    for match in _DATE_RANGE_PATTERN.finditer(search_text):
        month_name = match.group("month")
        start_year = match.group("start_year")
        year_only = match.group("year_only")
        if month_name and start_year:
            month = _MONTH_NAMES[month_name.lower()]
            start = date(int(start_year), month, 1)
        elif year_only:
            start = date(int(year_only), 1, 1)
        else:
            continue

        end = _parse_end_token(match.group("end"), reference_date)
        if end < start:
            continue
        ranges.append((start, end))
    return ranges


def _parse_month_year(token: str, reference_date: date) -> date:
    match = re.search(rf"(?i)({_MONTH})\s+(\d{{4}})", token)
    if not match:
        year_match = re.search(r"(\d{4})", token)
        if year_match:
            return date(int(year_match.group(1)), 1, 1)
        return reference_date
    month = _MONTH_NAMES[match.group(1).lower()]
    year = int(match.group(2))
    return date(year, month, 1)


def _parse_end_token(token: str, reference_date: date) -> date:
    if re.fullmatch(rf"(?i){_PRESENT}", token.strip()):
        return reference_date
    return _parse_month_year(token, reference_date)


def _merge_date_ranges(ranges: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda item: item[0])
    merged: list[tuple[date, date]] = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))
