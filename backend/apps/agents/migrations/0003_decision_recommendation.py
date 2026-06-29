# Generated manually for Phase 8

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("agents", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DecisionRecommendation",
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
                            ("pending", "Pending"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("summary", models.TextField(blank=True)),
                ("rationale", models.TextField(blank=True)),
                ("actions", models.JSONField(blank=True, default=list)),
                ("input_snapshot", models.JSONField(blank=True, default=dict)),
                ("prompt_name", models.CharField(blank=True, max_length=128)),
                ("prompt_version", models.PositiveIntegerField(default=1)),
                ("model_name", models.CharField(blank=True, max_length=128)),
                (
                    "agent_execution",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decision_recommendations",
                        to="agents.agentexecution",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="decision_recommendations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workflow_execution",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decision_recommendations",
                        to="workflows.workflowexecution",
                    ),
                ),
            ],
            options={
                "db_table": "decision_recommendations",
                "ordering": ["-created_at"],
            },
        ),
    ]
