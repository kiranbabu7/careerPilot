import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from careerpilot.models import BaseModel, SoftDeleteManager
from apps.users.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    avatar_url = models.URLField(blank=True)

    objects = UserManager()
    all_objects = models.Manager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email


class UserPreference(BaseModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    target_roles = models.JSONField(default=list, blank=True)
    target_locations = models.JSONField(default=list, blank=True)
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    remote_preference = models.CharField(max_length=32, default="flexible")
    locations_configured = models.BooleanField(default=False)
    career_goals = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    job_search_schedule_enabled = models.BooleanField(default=False)
    job_search_schedule_interval_minutes = models.IntegerField(null=True, blank=True)
    last_job_search_at = models.DateTimeField(null=True, blank=True)
    last_scheduled_run_at = models.DateTimeField(null=True, blank=True)
    next_scheduled_run_at = models.DateTimeField(null=True, blank=True)
    last_schedule_message = models.TextField(blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "user_preferences"

    def __str__(self) -> str:
        return f"Preferences for {self.user.email}"
