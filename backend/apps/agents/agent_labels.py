"""Display labels and metadata helpers for agent executions."""

from datetime import datetime

AGENT_LABELS: dict[str, str] = {
    "planner": "Planner",
    "job_search": "Job Search",
    "company_research": "Company Research",
    "job_evaluation": "Job Evaluation",
    "resume_tailor": "Resume Tailor",
    "cover_letter": "Cover Letter",
    "interview_prep": "Interview Prep",
    "decision": "Decision Agent",
}


def agent_label(agent_name: str) -> str:
    return AGENT_LABELS.get(agent_name, agent_name.replace("_", " ").title())


def duration_ms(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if not started_at or not completed_at:
        return None
    return int((completed_at - started_at).total_seconds() * 1000)


def extract_related_entities(output_data: dict | None) -> list[dict]:
    if not output_data:
        return []

    entities: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(entity_type: str, entity_id: str, label: str = "") -> None:
        if not entity_id:
            return
        key = (entity_type, entity_id)
        if key in seen:
            return
        seen.add(key)
        entities.append({"type": entity_type, "id": entity_id, "label": label})

    add("opportunity", str(output_data.get("opportunity_id", "")), "")

    for item in output_data.get("results", []) if isinstance(output_data.get("results"), list) else []:
        if not isinstance(item, dict):
            continue
        add(
            "opportunity",
            str(item.get("opportunity_id", "")),
            str(item.get("job_title", "") or item.get("company", "")),
        )
    add("application", str(output_data.get("application_id", "")), "")
    add("interview_plan", str(output_data.get("interview_plan_id", "")), "")
    add("material", str(output_data.get("material_id", "")), "")

    if isinstance(output_data.get("opportunity"), dict):
        opp = output_data["opportunity"]
        add("opportunity", str(opp.get("id", "")), str(opp.get("job_title", "")))

    if isinstance(output_data.get("material"), dict):
        material = output_data["material"]
        add("material", str(material.get("id", "")), str(material.get("material_type", "")))

    if isinstance(output_data.get("interview_plan"), dict):
        plan = output_data["interview_plan"]
        add("interview_plan", str(plan.get("id", "")), str(plan.get("job_title", "")))

    for action in output_data.get("actions", []) if isinstance(output_data.get("actions"), list) else []:
        if not isinstance(action, dict):
            continue
        add(
            str(action.get("action_type", "entity")),
            str(action.get("target_id", "")),
            str(action.get("title", "")),
        )

    return entities
