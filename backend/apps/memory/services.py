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

    def record_application_context(self, user, application, content: str) -> None:
        job = application.opportunity.job
        self.repo.create_entry(
            user=user,
            category="application",
            content=content[:500],
            metadata={
                "application_id": str(application.id),
                "opportunity_id": str(application.opportunity_id),
                "stage": application.stage,
                "job_title": job.title,
                "job_company": job.company,
            },
        )

    def record_interview_prep_context(self, user, plan, content: str) -> None:
        job = plan.opportunity.job
        self.repo.create_entry(
            user=user,
            category="interview_prep",
            content=content[:500],
            metadata={
                "interview_plan_id": str(plan.id),
                "opportunity_id": str(plan.opportunity_id),
                "application_id": str(plan.application_id) if plan.application_id else None,
                "job_title": job.title,
                "job_company": job.company,
                "model_name": plan.model_name,
            },
        )

    def record_decision_context(self, user, recommendation) -> None:
        self.repo.create_entry(
            user=user,
            category="decision",
            content=recommendation.summary[:500] if recommendation.summary else "Decision generated",
            metadata={
                "decision_recommendation_id": str(recommendation.id),
                "workflow_id": str(recommendation.workflow_execution_id)
                if recommendation.workflow_execution_id
                else None,
                "action_count": len(recommendation.actions or []),
                "model_name": recommendation.model_name,
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

    def record_application_created(self, user, application) -> ActivityEvent:
        job = application.opportunity.job
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.APPLICATION_CREATED,
            title="Application tracked",
            description=f"{job.title} at {job.company}",
            metadata={
                "application_id": str(application.id),
                "opportunity_id": str(application.opportunity_id),
                "stage": application.stage,
            },
        )

    def record_application_stage_changed(
        self, user, application, from_stage: str
    ) -> ActivityEvent:
        job = application.opportunity.job
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.APPLICATION_STAGE_CHANGED,
            title="Application stage updated",
            description=f"{job.title}: {from_stage} → {application.stage}",
            metadata={
                "application_id": str(application.id),
                "opportunity_id": str(application.opportunity_id),
                "from_stage": from_stage,
                "to_stage": application.stage,
            },
        )

    def record_interview_prep_generated(
        self, user, plan, application=None
    ) -> ActivityEvent:
        job = plan.opportunity.job
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.INTERVIEW_PREP_GENERATED,
            title="Interview prep generated",
            description=f"Prep plan for {job.title} at {job.company}",
            metadata={
                "interview_plan_id": str(plan.id),
                "opportunity_id": str(plan.opportunity_id),
                "application_id": str(application.id) if application else None,
                "interview_id": str(plan.interview_id) if plan.interview_id else None,
                "model_name": plan.model_name,
            },
        )

    def record_interview_scheduled(self, user, interview) -> ActivityEvent:
        job = interview.opportunity.job
        round_label = interview.round_label or "Interview"
        scheduled = (
            interview.scheduled_at.isoformat() if interview.scheduled_at else None
        )
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.APPLICATION_STAGE_CHANGED,
            title="Interview scheduled",
            description=f"{round_label} for {job.title} at {job.company}",
            metadata={
                "interview_id": str(interview.id),
                "application_id": str(interview.application_id)
                if interview.application_id
                else None,
                "opportunity_id": str(interview.opportunity_id),
                "scheduled_at": scheduled,
                "format": interview.format,
                "outcome": interview.outcome,
            },
        )

    def record_decision_generated(self, user, recommendation) -> ActivityEvent:
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.DECISION_GENERATED,
            title="Decision recommendation generated",
            description=recommendation.summary[:200] if recommendation.summary else "",
            metadata={
                "decision_recommendation_id": str(recommendation.id),
                "workflow_id": str(recommendation.workflow_execution_id)
                if recommendation.workflow_execution_id
                else None,
                "agent_execution_id": str(recommendation.agent_execution_id)
                if recommendation.agent_execution_id
                else None,
                "action_count": len(recommendation.actions or []),
            },
        )

    def record_scheduled_search(
        self,
        user,
        workflow,
        *,
        summary: str,
        metadata: dict | None = None,
    ) -> ActivityEvent:
        event_metadata = dict(metadata or {})
        if workflow is not None:
            event_metadata["workflow_id"] = str(workflow.id)
        status = event_metadata.get("status", "completed")
        title = (
            "Scheduled job search skipped"
            if status == "skipped"
            else "Scheduled job search completed"
        )
        return self.repo.create_event(
            user=user,
            event_type=ActivityEvent.EventType.SCHEDULED_SEARCH,
            title=title,
            description=summary,
            metadata=event_metadata,
        )

    def list_recent(self, user, limit: int = 20) -> list[ActivityEvent]:
        return self.repo.list_recent(user, limit=limit)
