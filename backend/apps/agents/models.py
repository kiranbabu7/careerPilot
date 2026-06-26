from django.conf import settings
from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


class AgentExecutionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class AgentExecution(BaseModel):
    workflow_execution = models.ForeignKey(
        "workflows.WorkflowExecution",
        on_delete=models.CASCADE,
        related_name="agent_executions",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_executions",
    )
    agent_name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=32,
        choices=AgentExecutionStatus.choices,
        default=AgentExecutionStatus.PENDING,
    )
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    reasoning_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "agent_executions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.agent_name} ({self.status})"
