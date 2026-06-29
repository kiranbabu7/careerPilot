from django.db import migrations, models


def empty_metadata():
    return {}


def backfill_null_metadata(apps, schema_editor):
    WorkflowMessage = apps.get_model("workflows", "WorkflowMessage")
    WorkflowMessage.objects.filter(metadata__isnull=True).update(metadata={})


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0003_workflowmessage_metadata"),
    ]

    operations = [
        migrations.RunPython(backfill_null_metadata, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="workflowmessage",
            name="metadata",
            field=models.JSONField(blank=True, db_default={}, default=empty_metadata),
        ),
    ]
