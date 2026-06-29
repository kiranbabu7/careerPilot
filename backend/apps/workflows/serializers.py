from rest_framework import serializers

from apps.workflows.intent import classify_workflow_intent
from apps.workflows.models import WorkflowExecution, WorkflowMessage


class WorkflowStartSerializer(serializers.Serializer):
    goal = serializers.CharField(min_length=3, max_length=2000)


class WorkflowTailorResumeSerializer(serializers.Serializer):
    opportunity_id = serializers.UUIDField(required=False)
    job_description = serializers.CharField(required=False, min_length=20, max_length=50000)
    title = serializers.CharField(required=False, max_length=512)
    company = serializers.CharField(required=False, max_length=512, allow_blank=True)

    def validate(self, attrs):
        opportunity_id = attrs.get("opportunity_id")
        job_description = (attrs.get("job_description") or "").strip()

        if opportunity_id and job_description:
            raise serializers.ValidationError(
                "Provide either opportunity_id or a custom job description, not both."
            )
        if not opportunity_id and not job_description:
            raise serializers.ValidationError(
                "Provide opportunity_id or a custom job description."
            )
        if job_description:
            title = (attrs.get("title") or "").strip()
            if not title:
                raise serializers.ValidationError(
                    {"title": "Title is required for a custom job description."}
                )
            attrs["title"] = title
            attrs["company"] = (attrs.get("company") or "Custom role").strip() or "Custom role"
            attrs["job_description"] = job_description
        return attrs


def _resolve_workflow_intent(obj: WorkflowExecution) -> str:
    result = obj.result or {}
    context = obj.context or {}
    intent = result.get("workflow_intent") or context.get("workflow_intent")
    if intent:
        return intent
    return classify_workflow_intent(obj.goal or "")


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


class WorkflowExecutionListSerializer(WorkflowExecutionSerializer):
    intent = serializers.SerializerMethodField()
    agent_run_count = serializers.SerializerMethodField()
    last_agent_at = serializers.SerializerMethodField()
    planned_agents = serializers.SerializerMethodField()

    class Meta(WorkflowExecutionSerializer.Meta):
        fields = WorkflowExecutionSerializer.Meta.fields + (
            "intent",
            "agent_run_count",
            "last_agent_at",
            "planned_agents",
        )

    def get_intent(self, obj: WorkflowExecution) -> str:
        return _resolve_workflow_intent(obj)

    def get_agent_run_count(self, obj: WorkflowExecution) -> int:
        if hasattr(obj, "agent_run_count"):
            return obj.agent_run_count
        return obj.agent_executions.count()

    def get_last_agent_at(self, obj: WorkflowExecution):
        if hasattr(obj, "last_agent_at") and obj.last_agent_at:
            return obj.last_agent_at
        latest = obj.agent_executions.order_by("-created_at").first()
        return latest.created_at if latest else None

    def get_planned_agents(self, obj: WorkflowExecution) -> list[str]:
        result = obj.result or {}
        context = obj.context or {}
        planned = result.get("planned_agents") or context.get("planned_agents")
        return planned if isinstance(planned, list) else []


class WorkflowMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowMessage
        fields = (
            "id",
            "role",
            "content",
            "actions",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class WorkflowPostMessageSerializer(serializers.Serializer):
    content = serializers.CharField(min_length=1, max_length=4000)


class WorkflowActionSerializer(serializers.Serializer):
    action_key = serializers.CharField(max_length=64)
    params = serializers.DictField(required=False, default=dict)
    confirmed = serializers.BooleanField(default=False)
