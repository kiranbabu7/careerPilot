import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_opportunity_evaluation_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("resumes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApplicationMaterial",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "material_type",
                    models.CharField(
                        choices=[
                            ("tailored_resume", "Tailored Resume"),
                            ("cover_letter", "Cover Letter"),
                        ],
                        max_length=32,
                    ),
                ),
                ("content", models.TextField()),
                ("prompt_name", models.CharField(max_length=128)),
                ("prompt_version", models.PositiveIntegerField(default=1)),
                ("model_name", models.CharField(max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="completed",
                        max_length=32,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "opportunity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="application_materials",
                        to="jobs.opportunity",
                    ),
                ),
                (
                    "source_resume",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="application_materials",
                        to="resumes.resume",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="application_materials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "application_materials",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="applicationmaterial",
            index=models.Index(
                fields=["user", "material_type"],
                name="application_user_id_8f0a2d_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="applicationmaterial",
            index=models.Index(
                fields=["opportunity", "material_type"],
                name="application_opportu_4c8b1e_idx",
            ),
        ),
    ]
