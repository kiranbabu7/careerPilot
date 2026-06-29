from django.conf import settings
from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


class MemoryEntry(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memory_entries",
    )
    category = models.CharField(max_length=64, default="general")
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "memory_entries"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.category}: {self.content[:50]}"


class ActivityEvent(BaseModel):
    class EventType(models.TextChoices):
        RESUME_UPLOADED = "resume_uploaded", "Resume uploaded"
        RESUME_ANALYZED = "resume_analyzed", "Resume analyzed"
        PREFERENCES_UPDATED = "preferences_updated", "Preferences updated"
        PROFILE_ENRICHED = "profile_enriched", "Profile enriched"
        PROFILE_UPDATED = "profile_updated", "Profile updated"
        WORKFLOW_STARTED = "workflow_started", "Workflow started"
        APPLICATION_CREATED = "application_created", "Application created"
        APPLICATION_STAGE_CHANGED = "application_stage_changed", "Application stage changed"
        INTERVIEW_PREP_GENERATED = "interview_prep_generated", "Interview prep generated"
        DECISION_GENERATED = "decision_generated", "Decision generated"
        SCHEDULED_SEARCH = "scheduled_search", "Scheduled job search"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_events",
    )
    event_type = models.CharField(max_length=64, choices=EventType.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "activity_events"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.title}"
