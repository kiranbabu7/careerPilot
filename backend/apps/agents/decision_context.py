"""Context assembly for the Decision Agent."""

import json

from apps.applications.repositories import ApplicationRepository, InterviewPlanRepository
from apps.jobs.repositories import OpportunityRepository
from apps.memory.services import ActivityService, MemoryService
from apps.resumes.repositories import ApplicationMaterialRepository
from apps.workflows.repositories import WorkflowRepository


def _format_opportunities(opportunities) -> str:
    if not opportunities:
        return "None yet."
    lines = []
    for opp in opportunities[:8]:
        job = opp.job
        score = opp.match_score if opp.match_score is not None else "—"
        lines.append(
            f"- {job.title} at {job.company} (status={opp.status}, match={score}) "
            f"[id={opp.id}]"
        )
    return "\n".join(lines)


def _format_applications(applications) -> str:
    if not applications:
        return "None tracked yet."
    lines = []
    for app in applications[:10]:
        job = app.opportunity.job
        lines.append(
            f"- {job.title} at {job.company} (stage={app.stage}, priority={app.priority}) "
            f"[application_id={app.id}, opportunity_id={app.opportunity_id}]"
        )
    return "\n".join(lines)


def _format_materials(materials) -> str:
    if not materials:
        return "None generated yet."
    lines = []
    for material in materials[:10]:
        lines.append(
            f"- {material.material_type} for opportunity {material.opportunity_id} "
            f"[material_id={material.id}]"
        )
    return "\n".join(lines)


def _format_interview_plans(plans) -> str:
    if not plans:
        return "None generated yet."
    lines = []
    for plan in plans[:8]:
        job = plan.opportunity.job
        lines.append(
            f"- {job.title} at {job.company} (stage context) "
            f"[interview_plan_id={plan.id}, opportunity_id={plan.opportunity_id}]"
        )
    return "\n".join(lines)


def _format_activity(events) -> str:
    if not events:
        return "No recent activity."
    lines = []
    for event in events[:10]:
        lines.append(f"- {event.title}: {event.description[:120]}")
    return "\n".join(lines)


def _format_workflows(workflows) -> str:
    if not workflows:
        return "No workflows yet."
    lines = []
    for workflow in workflows[:5]:
        result = workflow.result or {}
        lines.append(
            f"- {workflow.name} ({workflow.status}): "
            f"discovered={result.get('discovered_count', 0)}, "
            f"evaluated={result.get('evaluated_count', 0)}, "
            f"top_match={result.get('top_match_score', 0)} "
            f"[workflow_id={workflow.id}]"
        )
    return "\n".join(lines)


def build_decision_context(user, *, workflow=None) -> dict:
    opportunity_repo = OpportunityRepository()
    application_repo = ApplicationRepository()
    material_repo = ApplicationMaterialRepository()
    plan_repo = InterviewPlanRepository()
    workflow_repo = WorkflowRepository()
    activity_service = ActivityService()
    memory_service = MemoryService()

    opportunities = opportunity_repo.list_for_user(user, include_rejected=False)
    opportunities.sort(
        key=lambda opp: opp.match_score if opp.match_score is not None else -1,
        reverse=True,
    )
    applications = application_repo.list_for_user(user)
    materials = material_repo.list_for_user(user)
    interview_plans = plan_repo.list_for_user(user)
    recent_activity = activity_service.list_recent(user, limit=10)
    workflows = workflow_repo.list_for_user(user)
    memory_context = memory_service.get_user_context(user)

    goal = ""
    if workflow:
        goal = workflow.goal or workflow.name
    elif workflows:
        goal = workflows[0].goal or workflows[0].name

    context = {
        "goal": goal,
        "workflow_id": str(workflow.id) if workflow else None,
        "top_opportunities": [
            {
                "id": str(opp.id),
                "title": opp.job.title,
                "company": opp.job.company,
                "status": opp.status,
                "match_score": opp.match_score,
            }
            for opp in opportunities[:8]
        ],
        "applications": [
            {
                "id": str(app.id),
                "opportunity_id": str(app.opportunity_id),
                "stage": app.stage,
                "job_title": app.opportunity.job.title,
                "job_company": app.opportunity.job.company,
            }
            for app in applications[:10]
        ],
        "materials": [
            {
                "id": str(material.id),
                "opportunity_id": str(material.opportunity_id),
                "material_type": material.material_type,
            }
            for material in materials[:10]
        ],
        "interview_plans": [
            {
                "id": str(plan.id),
                "opportunity_id": str(plan.opportunity_id),
                "job_title": plan.opportunity.job.title,
            }
            for plan in interview_plans[:8]
        ],
        "recent_activity": [
            {
                "title": event.title,
                "description": event.description,
                "event_type": event.event_type,
            }
            for event in recent_activity
        ],
        "workflow_summaries": [
            {
                "id": str(wf.id),
                "name": wf.name,
                "status": wf.status,
                "result": wf.result or {},
            }
            for wf in workflows[:5]
        ],
        "memory_snippets": [
            entry["content"] for entry in memory_context.get("memories", [])[:5]
        ],
        "counts": {
            "opportunities": len(opportunities),
            "applications": len(applications),
            "materials": len(materials),
            "interview_plans": len(interview_plans),
        },
    }
    return context


def build_decision_prompt_variables(context: dict) -> dict:
    return {
        "goal": context.get("goal") or "Advance my job search",
        "top_opportunities": _format_opportunities_data(context.get("top_opportunities", [])),
        "applications": _format_applications_data(context.get("applications", [])),
        "materials": _format_materials_data(context.get("materials", [])),
        "interview_plans": _format_interview_plans_data(context.get("interview_plans", [])),
        "recent_activity": _format_activity_data(context.get("recent_activity", [])),
        "workflow_summaries": _format_workflows_data(context.get("workflow_summaries", [])),
        "memory_snippets": "\n".join(context.get("memory_snippets", [])) or "None.",
    }


def _format_opportunities_data(items: list[dict]) -> str:
    if not items:
        return "None yet."
    return "\n".join(
        f"- {item['title']} at {item['company']} (status={item['status']}, "
        f"match={item.get('match_score', '—')}) [id={item['id']}]"
        for item in items
    )


def _format_applications_data(items: list[dict]) -> str:
    if not items:
        return "None tracked yet."
    return "\n".join(
        f"- {item['job_title']} at {item['job_company']} (stage={item['stage']}) "
        f"[application_id={item['id']}, opportunity_id={item['opportunity_id']}]"
        for item in items
    )


def _format_materials_data(items: list[dict]) -> str:
    if not items:
        return "None generated yet."
    return "\n".join(
        f"- {item['material_type']} for opportunity {item['opportunity_id']} "
        f"[material_id={item['id']}]"
        for item in items
    )


def _format_interview_plans_data(items: list[dict]) -> str:
    if not items:
        return "None generated yet."
    return "\n".join(
        f"- {item['job_title']} [interview_plan_id={item['id']}, "
        f"opportunity_id={item['opportunity_id']}]"
        for item in items
    )


def _format_activity_data(items: list[dict]) -> str:
    if not items:
        return "No recent activity."
    return "\n".join(f"- {item['title']}: {item['description'][:120]}" for item in items)


def _format_workflows_data(items: list[dict]) -> str:
    if not items:
        return "No workflows yet."
    lines = []
    for item in items:
        result = item.get("result", {})
        lines.append(
            f"- {item['name']} ({item['status']}): discovered={result.get('discovered_count', 0)}, "
            f"evaluated={result.get('evaluated_count', 0)}, top_match={result.get('top_match_score', 0)} "
            f"[workflow_id={item['id']}]"
        )
    return "\n".join(lines)


def context_to_json(context: dict) -> dict:
    return json.loads(json.dumps(context, default=str))
