"""User memory and activity services."""

from apps.memory.models import ActivityEvent
from apps.memory.repositories import ActivityRepository, MemoryRepository


class MemoryService:
    def __init__(self, repo: MemoryRepository | None = None):
        self.repo = repo or MemoryRepository()

    def get_user_context(self, user) -> dict:
        return self.repo.get_context(user)

    def record_resume_context(self, user, resume) -> None:
        self.repo.create_entry(
            user=user,
            category="resume",
            content=f"Uploaded resume: {resume.original_filename}",
            metadata={
                "resume_id": str(resume.id),
                "filename": resume.original_filename,
                "file_size": resume.file_size,
            },
        )

    def record_analysis_context(self, user, resume, analysis) -> None:
        self.repo.create_entry(
            user=user,
            category="resume_analysis",
            content=analysis.raw_summary[:500] if analysis.raw_summary else "Resume analyzed",
            metadata={
                "resume_id": str(resume.id),
                "analysis_id": str(analysis.id),
                "health_score": analysis.health_score,
                "ats_score": analysis.ats_score,
                "model_name": analysis.model_name,
            },
        )

    def record_preferences_context(self, user, preference) -> None:
        self.repo.create_entry(
            user=user,
            category="preferences",
            content="Career preferences updated",
            metadata={
                "target_roles": preference.target_roles,
                "target_locations": preference.target_locations,
                "remote_preference": preference.remote_preference,
            },
        )

    def record_profile_enriched(self, user, fields_updated: list[str], updates: dict) -> None:
        field_list = ", ".join(fields_updated)
        self.repo.create_entry(
            user=user,
            category="profile_enrichment",
            content=f"Inferred profile fields from resume: {field_list}",
            metadata={
                "fields_updated": fields_updated,
                "inferred": updates,
            },
        )

    def record_workflow_context(self, user, workflow, plan_summary: str) -> None:
        self.repo.create_entry(
            user=user,
            category="workflow",
            content=plan_summary[:500] if plan_summary else f"Started workflow: {workflow.name}",
            metadata={
                "workflow_id": str(workflow.id),
                "goal": workflow.goal,
                "status": workflow.status,
            },
        )


class ActivityService:
    def __init__(self, repo: ActivityRepository | None = None):
        self.repo = repo or ActivityRepository()

    def record_resume_uploaded(self, user, resume) -> ActivityEvent:
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.RESUME_UPLOADED,
            title="Resume uploaded",
            description=f"Uploaded {resume.original_filename}",
            metadata={"resume_id": str(resume.id), "filename": resume.original_filename},
        )

    def record_resume_analyzed(self, user, resume, analysis) -> ActivityEvent:
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.RESUME_ANALYZED,
            title="Resume analyzed",
            description=(
                f"Health score: {analysis.health_score}, ATS score: {analysis.ats_score}"
            ),
            metadata={
                "resume_id": str(resume.id),
                "analysis_id": str(analysis.id),
                "health_score": analysis.health_score,
                "ats_score": analysis.ats_score,
                "model_name": analysis.model_name,
            },
        )

    def record_preferences_updated(self, user) -> ActivityEvent:
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.PREFERENCES_UPDATED,
            title="Career preferences updated",
            description="Your target roles, locations, and goals were saved.",
        )

    def record_profile_enriched(self, user, fields_updated: list[str]) -> ActivityEvent:
        field_list = ", ".join(fields_updated)
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.PROFILE_ENRICHED,
            title="Profile enriched from resume",
            description=f"CareerPilot inferred {field_list} from your resume analysis.",
            metadata={"fields_updated": fields_updated},
        )

    def record_workflow_started(self, user, workflow) -> ActivityEvent:
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.WORKFLOW_STARTED,
            title="Career goal workflow started",
            description=workflow.goal[:200] if workflow.goal else workflow.name,
            metadata={"workflow_id": str(workflow.id), "status": workflow.status},
        )

    def list_recent(self, user, limit: int = 20) -> list[ActivityEvent]:
        return self.repo.list_recent(user, limit=limit)
