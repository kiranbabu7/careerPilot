from django.conf import settings
from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


class WorkflowExecutionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class WorkflowExecution(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workflow_executions",
    )
    name = models.CharField(max_length=255)
    goal = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=WorkflowExecutionStatus.choices,
        default=WorkflowExecutionStatus.PENDING,
    )
    context = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "workflow_executions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"
