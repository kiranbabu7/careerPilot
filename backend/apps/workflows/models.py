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


class WorkflowMessageRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    SYSTEM = "system", "System"


def empty_metadata() -> dict:
    return {}


class WorkflowMessage(BaseModel):
    workflow = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workflow_messages",
    )
    role = models.CharField(max_length=16, choices=WorkflowMessageRole.choices)
    content = models.TextField()
    actions = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=empty_metadata, blank=True, db_default={})

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "workflow_messages"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.metadata is None:
            self.metadata = {}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.role} @ {self.workflow_id}"
