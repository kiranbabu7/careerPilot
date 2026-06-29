from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_userpreference_job_search_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreference",
            name="last_schedule_message",
            field=models.TextField(blank=True),
        ),
    ]
