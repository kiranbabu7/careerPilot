"""Shared context helpers for interview prep agent."""

from apps.resumes.repositories import (
    ApplicationMaterialRepository,
    ResumeAnalysisRepository,
    ResumeRepository,
)
from apps.users.repositories import UserPreferenceRepository

from apps.agents.material_context import (
    format_company_research,
    format_match_evaluation,
    format_resume_analysis,
)


def build_interview_context(user, opportunity, application=None, *, interview=None) -> dict:
    resume_repo = ResumeRepository()
    analysis_repo = ResumeAnalysisRepository()
    preference_repo = UserPreferenceRepository()
    material_repo = ApplicationMaterialRepository()

    active_resume = resume_repo.get_active_for_user(user)
    analysis = (
        analysis_repo.get_latest_for_resume(active_resume) if active_resume else None
    )
    preference, _ = preference_repo.get_or_create_for_user(user)
    job = opportunity.job
    evaluation = opportunity.evaluation or {}
    company_research = job.company_research or {}

    if interview and interview.job_description and not job.description:
        job_description = interview.job_description
    else:
        job_description = job.description

    tailored = material_repo.get_latest_for_opportunity(
        user, opportunity.id, "tailored_resume"
    )
    cover_letter = material_repo.get_latest_for_opportunity(
        user, opportunity.id, "cover_letter"
    )

    return {
        "active_resume": active_resume,
        "resume_analysis": analysis,
        "preferences": preference,
        "job": job,
        "job_description": job_description,
        "evaluation": evaluation,
        "company_research": company_research,
        "tailored_resume": tailored,
        "cover_letter": cover_letter,
        "application": application,
        "application_stage": application.stage if application else "not_started",
        "interview": interview,
        "interview_round": interview.round_label if interview else "",
        "interview_format": interview.format if interview else "",
        "interview_notes": interview.interviewer_notes if interview else "",
        "interview_scheduled_at": (
            interview.scheduled_at.isoformat()
            if interview and interview.scheduled_at
            else ""
        ),
    }


def build_interview_prompt_variables(context: dict) -> dict:
    job = context["job"]
    prefs = context["preferences"]
    evaluation = context["evaluation"]
    resume = context.get("active_resume")
    analysis = context.get("resume_analysis")
    tailored = context.get("tailored_resume")
    cover = context.get("cover_letter")

    variables = {
        "job_title": job.title,
        "job_company": job.company,
        "job_location": job.location or "Not specified",
        "is_remote": "Yes" if job.is_remote else "No",
        "job_description": (context.get("job_description") or job.description or "No description provided.")[:8000],
        "match_evaluation": format_match_evaluation(evaluation),
        "company_research": format_company_research(context["company_research"]),
        "target_roles": ", ".join(prefs.target_roles) or "Not specified",
        "target_locations": ", ".join(prefs.target_locations) or "Not specified",
        "remote_preference": prefs.remote_preference,
        "skills": ", ".join(prefs.skills) or "Not specified",
        "career_goals": prefs.career_goals or "Not specified",
        "resume_analysis": format_resume_analysis(analysis),
        "resume_text": (resume.extracted_text or "")[:12000] if resume else "No resume uploaded.",
        "tailored_resume": (
            tailored.content if tailored else "No tailored resume generated yet."
        ),
        "cover_letter": (
            cover.content[:4000] if cover else "No cover letter generated yet."
        ),
        "application_stage": context.get("application_stage", "not_started"),
        "interview_round": context.get("interview_round") or "Not specified",
        "interview_format": context.get("interview_format") or "Not specified",
        "interview_notes": context.get("interview_notes") or "None provided.",
        "interview_scheduled_at": context.get("interview_scheduled_at") or "Not scheduled",
    }
    return variables
