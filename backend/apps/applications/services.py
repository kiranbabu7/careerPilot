"""Application and interview activity helpers."""

from __future__ import annotations

import hashlib

from django.db import transaction

from apps.applications.models import (
    Application,
    ApplicationStage,
    Interview,
    InterviewFormat,
    InterviewOutcome,
    InterviewSource,
)
from apps.applications.repositories import (
    ApplicationRepository,
    InterviewRepository,
)
from apps.jobs.models import OpportunityStatus
from apps.jobs.repositories import JobRepository, OpportunityRepository
from apps.memory.services import ActivityService, MemoryService


class ApplicationActivityService:
    def __init__(
        self,
        activity_service: ActivityService | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.activity_service = activity_service or ActivityService()
        self.memory_service = memory_service or MemoryService()

    def record_application_created(self, user, application: Application) -> None:
        job = application.opportunity.job
        title = f"Application tracked: {job.title}"
        self.activity_service.record_application_created(user, application)
        self.memory_service.record_application_context(user, application, title)

    def record_stage_changed(
        self, user, application: Application, from_stage: str
    ) -> None:
        job = application.opportunity.job
        self.activity_service.record_application_stage_changed(
            user, application, from_stage
        )
        self.memory_service.record_application_context(
            user,
            application,
            f"Moved {job.title} from {from_stage} to {application.stage}",
        )

    def record_interview_prep_generated(
        self, user, plan, *, application: Application | None = None
    ) -> None:
        self.activity_service.record_interview_prep_generated(user, plan, application)
        job = plan.opportunity.job
        self.memory_service.record_interview_prep_context(
            user,
            plan,
            f"Interview prep generated for {job.title} at {job.company}",
        )

    def record_interview_scheduled(self, user, interview: Interview) -> None:
        job = interview.opportunity.job
        round_label = interview.round_label or "Interview"
        self.activity_service.record_interview_scheduled(user, interview)
        if interview.application:
            self.memory_service.record_application_context(
                user,
                interview.application,
                f"{round_label} scheduled for {job.title} at {job.company}",
            )


class InterviewService:
    def __init__(
        self,
        interview_repo: InterviewRepository | None = None,
        application_repo: ApplicationRepository | None = None,
        job_repo: JobRepository | None = None,
        opportunity_repo: OpportunityRepository | None = None,
        activity_service: ApplicationActivityService | None = None,
    ):
        self.interview_repo = interview_repo or InterviewRepository()
        self.application_repo = application_repo or ApplicationRepository()
        self.job_repo = job_repo or JobRepository()
        self.opportunity_repo = opportunity_repo or OpportunityRepository()
        self.activity_service = activity_service or ApplicationActivityService()

    @transaction.atomic
    def create_external(self, user, payload: dict) -> Interview:
        company = (payload.get("company") or "").strip()
        job_title = (payload.get("job_title") or "").strip()
        if not company or not job_title:
            raise ValueError("company and job_title are required.")

        job_description = (payload.get("job_description") or "").strip()
        dedupe_raw = f"external_interview:{job_title.lower()}:{company.lower()}"
        if job_description:
            description_hash = hashlib.sha256(job_description.encode()).hexdigest()[:16]
            dedupe_raw = f"{dedupe_raw}:{description_hash}"
        dedupe_key = hashlib.sha256(dedupe_raw.encode()).hexdigest()

        job = self.job_repo.get_by_dedupe_key(dedupe_key)
        if job is None:
            job = self.job_repo.create(
                source="external_interview",
                title=job_title,
                company=company,
                description=job_description,
                dedupe_key=dedupe_key,
            )
        elif job_description and not job.description:
            job.description = job_description
            job.save(update_fields=["description", "updated_at"])

        opportunity, _created = self.opportunity_repo.get_or_create_for_user_job(
            user,
            job,
            defaults={
                "status": OpportunityStatus.APPLIED,
                "source_agent": "external_interview",
                "match_context": "External interview tracked outside job search pipeline.",
            },
        )

        application, app_created = self.application_repo.create_from_opportunity(
            user,
            opportunity,
            stage=ApplicationStage.INTERVIEWING,
            notes=payload.get("application_notes", ""),
        )
        if application.stage != ApplicationStage.INTERVIEWING:
            self.application_repo.update(
                application,
                stage=ApplicationStage.INTERVIEWING,
                stage_notes="Interview scheduled",
            )

        interview_format = payload.get("format") or InterviewFormat.VIDEO
        if interview_format not in InterviewFormat.values:
            interview_format = InterviewFormat.VIDEO

        outcome = payload.get("outcome") or InterviewOutcome.SCHEDULED
        if outcome not in InterviewOutcome.values:
            outcome = InterviewOutcome.SCHEDULED

        interview = self.interview_repo.create(
            user=user,
            opportunity=opportunity,
            application=application,
            scheduled_at=payload.get("scheduled_at"),
            round_label=(payload.get("round_label") or "").strip(),
            format=interview_format,
            interviewer_notes=(payload.get("interviewer_notes") or "").strip(),
            outcome=outcome,
            job_description=job_description,
            source=InterviewSource.EXTERNAL,
        )

        if app_created:
            self.activity_service.record_application_created(user, application)
        self.activity_service.record_interview_scheduled(user, interview)
        return interview

    def update(self, user, interview_id, payload: dict) -> Interview | None:
        interview = self.interview_repo.get_for_user(user, interview_id)
        if interview is None:
            return None

        update_fields: dict = {}
        for field in (
            "scheduled_at",
            "round_label",
            "format",
            "interviewer_notes",
            "outcome",
            "job_description",
        ):
            if field in payload:
                update_fields[field] = payload[field]

        if "format" in update_fields and update_fields["format"] not in InterviewFormat.values:
            del update_fields["format"]
        if "outcome" in update_fields and update_fields["outcome"] not in InterviewOutcome.values:
            del update_fields["outcome"]

        return self.interview_repo.update(interview, **update_fields)
