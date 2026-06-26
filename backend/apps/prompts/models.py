from django.db import models

from careerpilot.models import BaseModel, SoftDeleteManager


class PromptVersion(BaseModel):
    name = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)
    template = models.TextField()
    variables = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "prompt_versions"
        ordering = ["name", "-version"]
        unique_together = [("name", "version")]

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
