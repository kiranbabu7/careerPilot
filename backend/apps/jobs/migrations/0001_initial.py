# Generated manually for Phase 4

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("workflows", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Job",
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
                ("external_id", models.CharField(blank=True, max_length=512)),
                ("source", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=512)),
                ("company", models.CharField(max_length=512)),
                ("location", models.CharField(blank=True, max_length=512)),
                ("is_remote", models.BooleanField(default=False)),
                (
                    "salary_min",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "salary_max",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                ("salary_currency", models.CharField(blank=True, max_length=8)),
                ("description", models.TextField(blank=True)),
                ("apply_url", models.URLField(blank=True, max_length=2048)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("dedupe_key", models.CharField(db_index=True, max_length=128)),
                ("company_research", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "db_table": "jobs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Opportunity",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("discovered", "Discovered"),
                            ("saved", "Saved"),
                            ("rejected", "Rejected"),
                            ("applied", "Applied"),
                        ],
                        default="discovered",
                        max_length=32,
                    ),
                ),
                (
                    "source_agent",
                    models.CharField(default="job_search", max_length=128),
                ),
                ("match_context", models.TextField(blank=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opportunities",
                        to="jobs.job",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opportunities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workflow_execution",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opportunities",
                        to="workflows.workflowexecution",
                    ),
                ),
            ],
            options={
                "db_table": "opportunities",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(
                fields=["source", "external_id"], name="jobs_source__a1b2c3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(fields=["dedupe_key"], name="jobs_dedupe__d4e5f6_idx"),
        ),
        migrations.AddIndex(
            model_name="opportunity",
            index=models.Index(
                fields=["user", "status"], name="opportuniti_user_id_g7h8i9_idx"
            ),
        ),
    ]
