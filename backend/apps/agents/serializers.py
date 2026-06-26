from rest_framework import serializers

from apps.agents.models import AgentExecution


class AgentExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentExecution
        fields = (
            "id",
            "workflow_execution",
            "agent_name",
            "status",
            "input_data",
            "output_data",
            "reasoning_summary",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
