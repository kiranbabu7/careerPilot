import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("applications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Interview",
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
                ("scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("round_label", models.CharField(blank=True, max_length=128)),
                (
                    "format",
                    models.CharField(
                        choices=[
                            ("phone", "Phone"),
                            ("video", "Video"),
                            ("onsite", "Onsite"),
                            ("take_home", "Take home"),
                            ("other", "Other"),
                        ],
                        default="video",
                        max_length=32,
                    ),
                ),
                ("interviewer_notes", models.TextField(blank=True)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                            ("passed", "Passed"),
                            ("rejected", "Rejected"),
                        ],
                        default="scheduled",
                        max_length=32,
                    ),
                ),
                ("job_description", models.TextField(blank=True)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("pipeline", "Pipeline"),
                            ("external", "External"),
                        ],
                        default="external",
                        max_length=32,
                    ),
                ),
                (
                    "application",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="interviews",
                        to="applications.application",
                    ),
                ),
                (
                    "opportunity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interviews",
                        to="jobs.opportunity",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "interviews",
                "ordering": ["-scheduled_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="interview",
            index=models.Index(
                fields=["user", "scheduled_at"], name="interviews_user_id_8a1f2c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="interview",
            index=models.Index(
                fields=["user", "outcome"], name="interviews_user_id_4b9e3d_idx"
            ),
        ),
        migrations.AddField(
            model_name="interviewplan",
            name="interview",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="interview_plans",
                to="applications.interview",
            ),
        ),
    ]
