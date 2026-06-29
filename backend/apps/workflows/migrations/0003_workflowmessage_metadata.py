from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0002_workflowmessage"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowmessage",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
