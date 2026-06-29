from rest_framework import serializers

from apps.jobs.scheduled_search import VALID_SCHEDULE_INTERVALS, compute_next_scheduled_run_at
from apps.users.models import User, UserPreference


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "avatar_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = (
            "id",
            "target_roles",
            "target_locations",
            "salary_min",
            "salary_max",
            "remote_preference",
            "career_goals",
            "skills",
            "job_search_schedule_enabled",
            "job_search_schedule_interval_minutes",
            "last_job_search_at",
            "last_scheduled_run_at",
            "next_scheduled_run_at",
            "last_schedule_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "last_job_search_at",
            "last_scheduled_run_at",
            "next_scheduled_run_at",
            "last_schedule_message",
            "created_at",
            "updated_at",
        )

    def validate_job_search_schedule_interval_minutes(self, value):
        if value is None:
            return value
        if value not in VALID_SCHEDULE_INTERVALS:
            raise serializers.ValidationError(
                "Interval must be one of: 60, 240, 720, 1440 minutes."
            )
        return value

    def validate(self, attrs):
        enabled = attrs.get("job_search_schedule_enabled")
        interval = attrs.get("job_search_schedule_interval_minutes")

        if enabled is True and interval is None:
            existing_interval = None
            if self.instance is not None:
                existing_interval = self.instance.job_search_schedule_interval_minutes
            if existing_interval is None:
                raise serializers.ValidationError(
                    {
                        "job_search_schedule_interval_minutes": (
                            "Interval is required when scheduled search is enabled."
                        )
                    }
                )
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()
