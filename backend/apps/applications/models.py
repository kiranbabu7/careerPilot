from django.conf import settings
from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


class ApplicationStage(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPLIED = "applied", "Applied"
    INTERVIEWING = "interviewing", "Interviewing"
    OFFER = "offer", "Offer"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


class ApplicationPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


APPLICATION_STAGE_ORDER = [
    ApplicationStage.DRAFT,
    ApplicationStage.APPLIED,
    ApplicationStage.INTERVIEWING,
    ApplicationStage.OFFER,
    ApplicationStage.REJECTED,
    ApplicationStage.WITHDRAWN,
]


class Application(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    opportunity = models.ForeignKey(
        "jobs.Opportunity",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    stage = models.CharField(
        max_length=32,
        choices=ApplicationStage.choices,
        default=ApplicationStage.APPLIED,
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    target_follow_up_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    priority = models.CharField(
        max_length=16,
        choices=ApplicationPriority.choices,
        default=ApplicationPriority.MEDIUM,
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "applications"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "opportunity"],
                name="unique_application_per_user_opportunity",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "stage"]),
        ]

    def __str__(self) -> str:
        return f"{self.opportunity.job.title} ({self.stage})"


class ApplicationStageEvent(BaseModel):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="stage_events",
    )
    from_stage = models.CharField(max_length=32, blank=True)
    to_stage = models.CharField(max_length=32)
    notes = models.TextField(blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "application_stage_events"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.from_stage or '—'} → {self.to_stage}"


class InterviewFormat(models.TextChoices):
    PHONE = "phone", "Phone"
    VIDEO = "video", "Video"
    ONSITE = "onsite", "Onsite"
    TAKE_HOME = "take_home", "Take home"
    OTHER = "other", "Other"


class InterviewOutcome(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    PASSED = "passed", "Passed"
    REJECTED = "rejected", "Rejected"


class InterviewSource(models.TextChoices):
    PIPELINE = "pipeline", "Pipeline"
    EXTERNAL = "external", "External"


class Interview(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interviews",
    )
    opportunity = models.ForeignKey(
        "jobs.Opportunity",
        on_delete=models.CASCADE,
        related_name="interviews",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.SET_NULL,
        related_name="interviews",
        null=True,
        blank=True,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    round_label = models.CharField(max_length=128, blank=True)
    format = models.CharField(
        max_length=32,
        choices=InterviewFormat.choices,
        default=InterviewFormat.VIDEO,
    )
    interviewer_notes = models.TextField(blank=True)
    outcome = models.CharField(
        max_length=32,
        choices=InterviewOutcome.choices,
        default=InterviewOutcome.SCHEDULED,
    )
    job_description = models.TextField(blank=True)
    source = models.CharField(
        max_length=32,
        choices=InterviewSource.choices,
        default=InterviewSource.EXTERNAL,
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "interviews"
        ordering = ["-scheduled_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "scheduled_at"]),
            models.Index(fields=["user", "outcome"]),
        ]

    def __str__(self) -> str:
        return f"{self.opportunity.job.title} ({self.round_label or self.outcome})"


class InterviewPlanStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class InterviewPlan(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_plans",
    )
    opportunity = models.ForeignKey(
        "jobs.Opportunity",
        on_delete=models.CASCADE,
        related_name="interview_plans",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.SET_NULL,
        related_name="interview_plans",
        null=True,
        blank=True,
    )
    interview = models.ForeignKey(
        Interview,
        on_delete=models.SET_NULL,
        related_name="interview_plans",
        null=True,
        blank=True,
    )
    prompt_name = models.CharField(max_length=128)
    prompt_version = models.PositiveIntegerField(default=1)
    model_name = models.CharField(max_length=128)
    content = models.JSONField(default=dict, blank=True)
    markdown = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=InterviewPlanStatus.choices,
        default=InterviewPlanStatus.COMPLETED,
    )
    metadata = models.JSONField(default=dict, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "interview_plans"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"Interview plan for {self.opportunity.job.title}"
