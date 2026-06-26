from django.conf import settings
from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


class OpportunityStatus(models.TextChoices):
    DISCOVERED = "discovered", "Discovered"
    SAVED = "saved", "Saved"
    REJECTED = "rejected", "Rejected"
    APPLIED = "applied", "Applied"


class Job(BaseModel):
    external_id = models.CharField(max_length=512, blank=True)
    source = models.CharField(max_length=64)
    title = models.CharField(max_length=512)
    company = models.CharField(max_length=512)
    location = models.CharField(max_length=512, blank=True)
    is_remote = models.BooleanField(default=False)
    salary_min = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    salary_max = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    salary_currency = models.CharField(max_length=8, blank=True)
    description = models.TextField(blank=True)
    apply_url = models.URLField(max_length=2048, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=128, db_index=True)
    company_research = models.JSONField(default=dict, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "external_id"]),
            models.Index(fields=["dedupe_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} at {self.company}"


class Opportunity(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="opportunities",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="opportunities",
    )
    workflow_execution = models.ForeignKey(
        "workflows.WorkflowExecution",
        on_delete=models.CASCADE,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=OpportunityStatus.choices,
        default=OpportunityStatus.DISCOVERED,
    )
    source_agent = models.CharField(max_length=128, default="job_search")
    match_context = models.TextField(blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "opportunities"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.job.title} ({self.status})"
