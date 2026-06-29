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


class ApplicationMaterialType(models.TextChoices):
    TAILORED_RESUME = "tailored_resume", "Tailored Resume"
    COVER_LETTER = "cover_letter", "Cover Letter"


class ApplicationMaterialStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ApplicationMaterial(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="application_materials",
    )
    opportunity = models.ForeignKey(
        "jobs.Opportunity",
        on_delete=models.CASCADE,
        related_name="application_materials",
    )
    source_resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="application_materials",
    )
    material_type = models.CharField(
        max_length=32,
        choices=ApplicationMaterialType.choices,
    )
    content = models.TextField()
    prompt_name = models.CharField(max_length=128)
    prompt_version = models.PositiveIntegerField(default=1)
    model_name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=32,
        choices=ApplicationMaterialStatus.choices,
        default=ApplicationMaterialStatus.COMPLETED,
    )
    metadata = models.JSONField(default=dict, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "application_materials"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "material_type"]),
            models.Index(fields=["opportunity", "material_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.material_type} for {self.opportunity_id}"
