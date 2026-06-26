from rest_framework import serializers

from apps.workflows.models import WorkflowExecution


class WorkflowStartSerializer(serializers.Serializer):
    goal = serializers.CharField(min_length=3, max_length=2000)


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowExecution
        fields = (
            "id",
            "name",
            "goal",
            "status",
            "context",
            "result",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
