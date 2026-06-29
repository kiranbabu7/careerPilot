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


class DecisionRecommendationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class DecisionRecommendation(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="decision_recommendations",
    )
    workflow_execution = models.ForeignKey(
        "workflows.WorkflowExecution",
        on_delete=models.SET_NULL,
        related_name="decision_recommendations",
        null=True,
        blank=True,
    )
    agent_execution = models.ForeignKey(
        AgentExecution,
        on_delete=models.SET_NULL,
        related_name="decision_recommendations",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=DecisionRecommendationStatus.choices,
        default=DecisionRecommendationStatus.PENDING,
    )
    summary = models.TextField(blank=True)
    rationale = models.TextField(blank=True)
    actions = models.JSONField(default=list, blank=True)
    input_snapshot = models.JSONField(default=dict, blank=True)
    prompt_name = models.CharField(max_length=128, blank=True)
    prompt_version = models.PositiveIntegerField(default=1)
    model_name = models.CharField(max_length=128, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "decision_recommendations"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Decision ({self.status})"
