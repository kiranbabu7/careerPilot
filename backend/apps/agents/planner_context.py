"""Context assembly for the Planner Agent."""

import json

from apps.applications.repositories import ApplicationRepository, InterviewPlanRepository
from apps.memory.services import MemoryService
from apps.resumes.repositories import ApplicationMaterialRepository, ResumeAnalysisRepository, ResumeRepository
from apps.users.repositories import UserPreferenceRepository
from apps.workflows.intent import classify_workflow_intent


def _format_list(items: list, *, empty: str = "None") -> str:
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def build_planner_context(
    user,
    goal: str,
    *,
    workflow_intent: str | None = None,
    preference_repo: UserPreferenceRepository | None = None,
    resume_repo: ResumeRepository | None = None,
    analysis_repo: ResumeAnalysisRepository | None = None,
    memory_service: MemoryService | None = None,
    application_repo: ApplicationRepository | None = None,
    material_repo: ApplicationMaterialRepository | None = None,
    interview_plan_repo: InterviewPlanRepository | None = None,
) -> dict:
    """Build structured context for planner prompts (mirrors PlannerAgent.build_context)."""
    preference_repo = preference_repo or UserPreferenceRepository()
    resume_repo = resume_repo or ResumeRepository()
    analysis_repo = analysis_repo or ResumeAnalysisRepository()
    memory_service = memory_service or MemoryService()
    application_repo = application_repo or ApplicationRepository()
    material_repo = material_repo or ApplicationMaterialRepository()
    interview_plan_repo = interview_plan_repo or InterviewPlanRepository()

    preference, _ = preference_repo.get_or_create_for_user(user)
    resolved_intent = workflow_intent or classify_workflow_intent(goal)
    active_resume = resume_repo.get_active_for_user(user)
    active_analysis = (
        analysis_repo.get_latest_for_resume(active_resume)
        if active_resume
        else None
    )
    memory_context = memory_service.get_user_context(user)

    return {
        "goal": goal,
        "workflow_intent": resolved_intent,
        "preferences": {
            "target_roles": preference.target_roles,
            "target_locations": preference.target_locations,
            "remote_preference": preference.remote_preference,
            "career_goals": preference.career_goals,
            "skills": preference.skills,
        },
        "active_resume": (
            {
                "id": str(active_resume.id),
                "filename": active_resume.original_filename,
                "health_score": active_analysis.health_score if active_analysis else None,
                "ats_score": active_analysis.ats_score if active_analysis else None,
            }
            if active_resume
            else None
        ),
        "memory_snippets": [
            entry["content"] for entry in memory_context.get("memories", [])[:5]
        ],
        "pipeline_counts": {
            "applications": len(application_repo.list_for_user(user)),
            "materials": len(material_repo.list_for_user(user)),
            "interview_plans": len(interview_plan_repo.list_for_user(user)),
        },
    }


def build_planner_prompt_variables(context: dict) -> dict:
    prefs = context.get("preferences") or {}
    resume = context.get("active_resume")
    resume_line = (
        f"{resume['filename']} (health {resume.get('health_score', '—')})"
        if resume
        else "No active resume uploaded."
    )
    memory = context.get("memory_snippets") or []
    pipeline = context.get("pipeline_counts") or {}

    return {
        "goal": context.get("goal", ""),
        "workflow_intent": context.get("workflow_intent", "job_discovery"),
        "target_roles": _format_list(prefs.get("target_roles") or [], empty="Not set"),
        "target_locations": _format_list(
            prefs.get("target_locations") or [], empty="Not set"
        ),
        "remote_preference": prefs.get("remote_preference") or "flexible",
        "skills": _format_list(prefs.get("skills") or [], empty="Not set"),
        "career_goals": (prefs.get("career_goals") or "").strip() or "Not set",
        "active_resume": resume_line,
        "memory_snippets": _format_list(memory, empty="No memory snippets yet."),
        "pipeline_summary": (
            f"{pipeline.get('applications', 0)} applications, "
            f"{pipeline.get('materials', 0)} materials, "
            f"{pipeline.get('interview_plans', 0)} interview plans"
        ),
    }


def build_replan_prompt_variables(
    *,
    goal: str,
    context: dict,
    tool_plan: list,
    workflow_result: dict,
    last_tool_result: dict,
    execution_summaries: list[str],
    recent_messages: list[str],
) -> dict:
    base = build_planner_prompt_variables(context)
    base.update(
        {
            "current_tool_plan": json.dumps(tool_plan, indent=2),
            "workflow_result_summary": json.dumps(
                {
                    k: workflow_result.get(k)
                    for k in (
                        "discovered_count",
                        "evaluated_count",
                        "accepted_count",
                        "top_match_score",
                        "constraints",
                        "completed_agents",
                    )
                    if k in workflow_result
                },
                indent=2,
            ),
            "last_tool_result": json.dumps(last_tool_result, indent=2),
            "execution_summaries": _format_list(
                execution_summaries, empty="No prior tool runs."
            ),
            "recent_messages": _format_list(recent_messages, empty="No chat messages yet."),
            "goal": goal,
        }
    )
    return base


def context_to_json(context: dict) -> dict:
    """JSON-serializable snapshot for AgentExecution input_data."""
    return json.loads(json.dumps(context, default=str))
