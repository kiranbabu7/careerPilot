from rest_framework import serializers

from apps.agents.agent_labels import (
    agent_label,
    duration_ms,
    extract_related_entities,
)
from apps.agents.models import AgentExecution, DecisionRecommendation


class AgentExecutionSummarySerializer(serializers.ModelSerializer):
    agent_label = serializers.SerializerMethodField()
    duration_ms = serializers.SerializerMethodField()
    has_error = serializers.SerializerMethodField()
    related_entities = serializers.SerializerMethodField()
    workflow_goal = serializers.SerializerMethodField()
    workflow_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentExecution
        fields = (
            "id",
            "workflow_execution",
            "workflow_goal",
            "workflow_name",
            "agent_name",
            "agent_label",
            "status",
            "reasoning_summary",
            "error_message",
            "has_error",
            "started_at",
            "completed_at",
            "duration_ms",
            "related_entities",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_agent_label(self, obj: AgentExecution) -> str:
        return agent_label(obj.agent_name)

    def get_duration_ms(self, obj: AgentExecution) -> int | None:
        return duration_ms(obj.started_at, obj.completed_at)

    def get_has_error(self, obj: AgentExecution) -> bool:
        return bool(obj.error_message) or obj.status == "failed"

    def get_related_entities(self, obj: AgentExecution) -> list[dict]:
        return extract_related_entities(obj.output_data)

    def get_workflow_goal(self, obj: AgentExecution) -> str | None:
        workflow = obj.workflow_execution
        return workflow.goal if workflow else None

    def get_workflow_name(self, obj: AgentExecution) -> str | None:
        workflow = obj.workflow_execution
        return workflow.name if workflow else None


class AgentExecutionDetailSerializer(AgentExecutionSummarySerializer):
    class Meta(AgentExecutionSummarySerializer.Meta):
        fields = AgentExecutionSummarySerializer.Meta.fields + (
            "input_data",
            "output_data",
        )


class AgentExecutionSerializer(AgentExecutionDetailSerializer):
    """Backward-compatible full serializer used by workflow detail responses."""

    pass


class PaginatedAgentExecutionSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = AgentExecutionSummarySerializer(many=True)


class DecisionActionSerializer(serializers.Serializer):
    action_type = serializers.CharField()
    target_id = serializers.CharField(allow_blank=True, required=False)
    title = serializers.CharField()
    reason = serializers.CharField()
    urgency = serializers.CharField()
    route = serializers.CharField()


class DecisionRecommendationSummarySerializer(serializers.ModelSerializer):
    action_count = serializers.SerializerMethodField()
    agent_execution_id = serializers.SerializerMethodField()

    class Meta:
        model = DecisionRecommendation
        fields = (
            "id",
            "workflow_execution",
            "agent_execution_id",
            "status",
            "summary",
            "action_count",
            "model_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_action_count(self, obj: DecisionRecommendation) -> int:
        return len(obj.actions or [])

    def get_agent_execution_id(self, obj: DecisionRecommendation) -> str | None:
        return str(obj.agent_execution_id) if obj.agent_execution_id else None


class DecisionRecommendationDetailSerializer(DecisionRecommendationSummarySerializer):
    actions = DecisionActionSerializer(many=True)
    rationale = serializers.CharField()
    input_snapshot = serializers.JSONField()
    prompt_name = serializers.CharField()
    prompt_version = serializers.IntegerField()
    agent_execution = AgentExecutionSummarySerializer(read_only=True)

    class Meta(DecisionRecommendationSummarySerializer.Meta):
        fields = DecisionRecommendationSummarySerializer.Meta.fields + (
            "rationale",
            "actions",
            "input_snapshot",
            "prompt_name",
            "prompt_version",
            "agent_execution",
        )


class PaginatedDecisionRecommendationSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = DecisionRecommendationSummarySerializer(many=True)


class DecisionGenerateSerializer(serializers.Serializer):
    workflow_id = serializers.UUIDField(required=False, allow_null=True)
