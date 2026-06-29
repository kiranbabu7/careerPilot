"""Application and interview plan persistence."""

from django.db import transaction
from django.utils import timezone

from apps.applications.models import (
    APPLICATION_STAGE_ORDER,
    Application,
    ApplicationPriority,
    ApplicationStage,
    ApplicationStageEvent,
    Interview,
    InterviewPlan,
)
from apps.jobs.models import Opportunity, OpportunityStatus
from apps.jobs.repositories import OpportunityRepository


class ApplicationRepository:
    def get_for_user(self, user, application_id) -> Application | None:
        return (
            Application.objects.filter(user=user, id=application_id)
            .select_related("opportunity", "opportunity__job")
            .first()
        )

    def get_for_opportunity(self, user, opportunity_id) -> Application | None:
        return (
            Application.objects.filter(user=user, opportunity_id=opportunity_id)
            .select_related("opportunity", "opportunity__job")
            .first()
        )

    def list_for_user(self, user) -> list[Application]:
        return list(
            Application.objects.filter(user=user)
            .select_related("opportunity", "opportunity__job")
            .order_by("-updated_at")
        )

    def list_by_stage(self, user) -> dict[str, list[Application]]:
        applications = self.list_for_user(user)
        grouped: dict[str, list[Application]] = {
            stage.value: [] for stage in APPLICATION_STAGE_ORDER
        }
        for application in applications:
            grouped.setdefault(application.stage, []).append(application)
        return grouped

    @transaction.atomic
    def create_from_opportunity(
        self,
        user,
        opportunity: Opportunity,
        *,
        stage: str = ApplicationStage.APPLIED,
        notes: str = "",
        priority: str | None = None,
    ) -> tuple[Application, bool]:
        existing = self.get_for_opportunity(user, opportunity.id)
        if existing:
            return existing, False

        applied_at = timezone.now() if stage == ApplicationStage.APPLIED else None
        application = Application.objects.create(
            user=user,
            opportunity=opportunity,
            stage=stage,
            applied_at=applied_at,
            notes=notes,
            priority=priority or ApplicationPriority.MEDIUM,
        )
        ApplicationStageEvent.objects.create(
            application=application,
            from_stage="",
            to_stage=stage,
            notes="Application created",
        )

        if opportunity.status != OpportunityStatus.APPLIED:
            OpportunityRepository().update_status(opportunity, OpportunityStatus.APPLIED)

        return application, True

    def update(
        self,
        application: Application,
        *,
        stage: str | None = None,
        notes: str | None = None,
        priority: str | None = None,
        target_follow_up_at=None,
        stage_notes: str = "",
    ) -> Application:
        update_fields = ["updated_at"]
        if notes is not None:
            application.notes = notes
            update_fields.append("notes")
        if priority is not None:
            application.priority = priority
            update_fields.append("priority")
        if target_follow_up_at is not None:
            application.target_follow_up_at = target_follow_up_at
            update_fields.append("target_follow_up_at")

        if stage is not None and stage != application.stage:
            from_stage = application.stage
            application.stage = stage
            update_fields.append("stage")
            if stage == ApplicationStage.APPLIED and not application.applied_at:
                application.applied_at = timezone.now()
                update_fields.append("applied_at")
            application.save(update_fields=update_fields)
            ApplicationStageEvent.objects.create(
                application=application,
                from_stage=from_stage,
                to_stage=stage,
                notes=stage_notes,
            )
            return application

        application.save(update_fields=update_fields)
        return application

    def list_stage_events(self, application: Application) -> list[ApplicationStageEvent]:
        return list(application.stage_events.order_by("-created_at"))


class InterviewPlanRepository:
    def create(self, **fields) -> InterviewPlan:
        return InterviewPlan.objects.create(**fields)

    def get_for_user(self, user, plan_id) -> InterviewPlan | None:
        return (
            InterviewPlan.objects.filter(user=user, id=plan_id)
            .select_related(
                "opportunity",
                "opportunity__job",
                "application",
            )
            .first()
        )

    def list_for_user(self, user) -> list[InterviewPlan]:
        return list(
            InterviewPlan.objects.filter(user=user)
            .select_related(
                "opportunity",
                "opportunity__job",
                "application",
            )
            .order_by("-created_at")
        )

    def list_for_application(self, user, application_id) -> list[InterviewPlan]:
        return list(
            InterviewPlan.objects.filter(user=user, application_id=application_id)
            .select_related("opportunity", "opportunity__job")
            .order_by("-created_at")
        )

    def list_for_opportunity(self, user, opportunity_id) -> list[InterviewPlan]:
        return list(
            InterviewPlan.objects.filter(user=user, opportunity_id=opportunity_id)
            .select_related("opportunity", "opportunity__job", "application", "interview")
            .order_by("-created_at")
        )


class InterviewRepository:
    def create(self, **fields) -> Interview:
        return Interview.objects.create(**fields)

    def get_for_user(self, user, interview_id) -> Interview | None:
        return (
            Interview.objects.filter(user=user, id=interview_id)
            .select_related(
                "opportunity",
                "opportunity__job",
                "application",
            )
            .first()
        )

    def list_for_user(self, user) -> list[Interview]:
        return list(
            Interview.objects.filter(user=user)
            .select_related(
                "opportunity",
                "opportunity__job",
                "application",
            )
            .order_by("-scheduled_at", "-created_at")
        )

    def update(self, interview: Interview, **fields) -> Interview:
        update_fields = ["updated_at"]
        for key, value in fields.items():
            if value is not None or key in (
                "scheduled_at",
                "round_label",
                "interviewer_notes",
                "job_description",
            ):
                setattr(interview, key, value)
                update_fields.append(key)
        interview.save(update_fields=update_fields)
        return interview
