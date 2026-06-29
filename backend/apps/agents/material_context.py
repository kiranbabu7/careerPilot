"""Shared context helpers for application material agents."""

from datetime import date

from apps.resumes.repositories import (
    ApplicationMaterialRepository,
    ResumeAnalysisRepository,
    ResumeRepository,
)
from apps.resumes.resume_content import (
    compute_years_of_experience,
    extract_contact_from_sources,
    format_years_of_experience_constraint,
)
from apps.users.repositories import UserPreferenceRepository


class NoActiveResumeError(Exception):
    pass


def build_material_context(user, opportunity) -> dict:
    resume_repo = ResumeRepository()
    analysis_repo = ResumeAnalysisRepository()
    preference_repo = UserPreferenceRepository()
    material_repo = ApplicationMaterialRepository()

    active_resume = resume_repo.get_active_for_user(user)
    if not active_resume:
        raise NoActiveResumeError(
            "No active resume found. Upload and activate a resume before generating materials."
        )

    analysis = analysis_repo.get_latest_for_resume(active_resume)
    preference, _ = preference_repo.get_or_create_for_user(user)
    job = opportunity.job
    evaluation = opportunity.evaluation or {}
    company_research = job.company_research or {}

    tailored = material_repo.get_latest_for_opportunity(
        user, opportunity.id, "tailored_resume"
    )

    return {
        "user": user,
        "active_resume": active_resume,
        "resume_analysis": analysis,
        "preferences": preference,
        "job": job,
        "evaluation": evaluation,
        "company_research": company_research,
        "tailored_resume": tailored,
    }


def format_match_evaluation(evaluation: dict) -> str:
    if not evaluation:
        return "No match evaluation available yet."
    lines = [
        f"Score: {evaluation.get('match_score', '—')}/100",
        f"Recommendation: {evaluation.get('recommendation', '—')}",
        f"Rationale: {evaluation.get('rationale', '')}",
    ]
    strengths = evaluation.get("strengths") or []
    gaps = evaluation.get("gaps") or []
    if strengths:
        lines.append("Strengths: " + "; ".join(strengths))
    if gaps:
        lines.append("Gaps: " + "; ".join(gaps))
    return "\n".join(lines)


def format_company_research(research: dict) -> str:
    if not research:
        return "No company research available."
    if not research.get("available", True) and not research.get("summary"):
        reason = research.get("reason", "unavailable")
        return f"Company research unavailable ({reason})."
    parts = []
    section_labels = (
        ("summary", "Overview"),
        ("what_they_do", "What they do"),
        ("recent_news", "Recent news"),
        ("funding", "Funding"),
        ("hiring_signals", "Hiring signals"),
    )
    for key, label in section_labels:
        value = research.get(key)
        if value:
            parts.append(f"{label}: {value}")
    if not parts and research.get("summary"):
        parts.append(research["summary"])
    for snippet in research.get("snippets") or []:
        title = snippet.get("title", "")
        text = snippet.get("snippet", "")
        parts.append(f"- {title}: {text}" if title else f"- {text}")
    return "\n".join(parts) or "No company research details."


def format_resume_analysis(analysis) -> str:
    if not analysis:
        return "No resume analysis available."
    return (
        f"Health score: {analysis.health_score}/100, "
        f"ATS score: {analysis.ats_score}/100. "
        f"{analysis.raw_summary}"
    )


def format_candidate_contact(context: dict) -> dict[str, str]:
    """Contact fields for prompts and material generation."""
    user = context.get("user")
    resume = context.get("active_resume")
    prefs = context.get("preferences")
    resume_text = (resume.extracted_text or "") if resume else ""
    target_locations = list(prefs.target_locations or []) if prefs else []
    if user:
        contact = extract_contact_from_sources(
            user=user,
            resume_text=resume_text,
            target_locations=target_locations,
        )
    else:
        from apps.resumes.resume_content import ResumeContact

        contact = ResumeContact(full_name="Candidate")

    return {
        "candidate_name": contact.full_name,
        "candidate_email": contact.email or "Not provided",
        "candidate_phone": contact.phone or "Not provided",
        "candidate_location": contact.location or "Not provided",
    }


def build_prompt_variables(context: dict, *, include_tailored: bool = False) -> dict:
    job = context["job"]
    prefs = context["preferences"]
    evaluation = context["evaluation"]
    analysis = context["resume_analysis"]
    resume = context["active_resume"]
    resume_text = (resume.extracted_text or "")[:12000]
    reference_date = date.today()
    years = compute_years_of_experience(resume_text, reference_date=reference_date)
    contact = format_candidate_contact(context)

    variables = {
        "job_title": job.title,
        "job_company": job.company,
        "job_location": job.location or "Not specified",
        "is_remote": "Yes" if job.is_remote else "No",
        "job_description": (job.description or "No description provided.")[:8000],
        "match_evaluation": format_match_evaluation(evaluation),
        "company_research": format_company_research(context["company_research"]),
        "target_roles": ", ".join(prefs.target_roles) or "Not specified",
        "target_locations": ", ".join(prefs.target_locations) or "Not specified",
        "remote_preference": prefs.remote_preference,
        "skills": ", ".join(prefs.skills) or "Not specified",
        "career_goals": prefs.career_goals or "Not specified",
        "resume_analysis": format_resume_analysis(analysis),
        "resume_text": resume_text,
        "years_of_experience": format_years_of_experience_constraint(
            years,
            reference_date=reference_date,
        ),
        "letter_date": reference_date.strftime("%B %d, %Y"),
        **contact,
    }
    if include_tailored:
        tailored = context.get("tailored_resume")
        variables["tailored_resume"] = (
            tailored.content if tailored else "No tailored resume generated yet."
        )
    return variables
