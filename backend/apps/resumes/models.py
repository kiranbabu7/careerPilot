from django.conf import settings
from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


def resume_upload_path(instance: "Resume", filename: str) -> str:
    return f"resumes/{instance.user_id}/{filename}"


class Resume(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resumes",
    )
    file = models.FileField(upload_to=resume_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    extracted_text = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "resumes"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.user_id})"


class ResumeAnalysis(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="analyses",
    )
    model_name = models.CharField(max_length=128)
    raw_summary = models.TextField(blank=True)
    health_score = models.PositiveSmallIntegerField(default=0)
    ats_score = models.PositiveSmallIntegerField(default=0)
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    missing_keywords = models.JSONField(default=list, blank=True)
    improvement_suggestions = models.JSONField(default=list, blank=True)
    extracted_skills = models.JSONField(default=list, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "resume_analyses"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Analysis for {self.resume_id} ({self.model_name})"
