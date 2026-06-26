from rest_framework import serializers

from apps.memory.models import ActivityEvent, MemoryEntry


class MemoryEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MemoryEntry
        fields = ("id", "category", "content", "metadata", "created_at")
        read_only_fields = fields


class ActivityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityEvent
        fields = (
            "id",
            "event_type",
            "title",
            "description",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class DashboardSummarySerializer(serializers.Serializer):
    profile_completion = serializers.IntegerField()
    completion_signals = serializers.DictField()
    active_resume = serializers.DictField(allow_null=True)
    preferences_summary = serializers.DictField()
    recent_activity = ActivityEventSerializer(many=True)
    next_actions = serializers.ListField(child=serializers.DictField())
