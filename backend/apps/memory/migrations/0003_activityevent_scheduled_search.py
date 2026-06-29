from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("memory", "0002_activity_decision_event"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activityevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("resume_uploaded", "Resume uploaded"),
                    ("resume_analyzed", "Resume analyzed"),
                    ("preferences_updated", "Preferences updated"),
                    ("profile_enriched", "Profile enriched"),
                    ("profile_updated", "Profile updated"),
                    ("workflow_started", "Workflow started"),
                    ("application_created", "Application created"),
                    ("application_stage_changed", "Application stage changed"),
                    ("interview_prep_generated", "Interview prep generated"),
                    ("decision_generated", "Decision generated"),
                    ("scheduled_search", "Scheduled job search"),
                ],
                max_length=64,
            ),
        ),
    ]
