from django.db import migrations, models


def backfill_locations_configured(apps, schema_editor):
    UserPreference = apps.get_model("users", "UserPreference")
    for preference in UserPreference.objects.all().iterator():
        if preference.locations_configured:
            continue
        has_locations = bool(preference.target_locations)
        has_non_default_remote = preference.remote_preference != "flexible"
        if has_locations or has_non_default_remote:
            preference.locations_configured = True
            preference.save(update_fields=["locations_configured"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_userpreference_last_schedule_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreference",
            name="locations_configured",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            backfill_locations_configured,
            migrations.RunPython.noop,
        ),
    ]
