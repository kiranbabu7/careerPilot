from rest_framework import serializers

from apps.applications.models import (
    APPLICATION_STAGE_ORDER,
    Application,
    ApplicationPriority,
    ApplicationStage,
    ApplicationStageEvent,
    Interview,
    InterviewFormat,
    InterviewOutcome,
    InterviewPlan,
)
from apps.jobs.serializers import JobSerializer, OpportunityListSerializer
from apps.resumes.serializers import ApplicationMaterialSerializer


class ApplicationStageEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationStageEvent
        fields = (
            "id",
            "from_stage",
            "to_stage",
            "notes",
            "created_at",
        )
        read_only_fields = fields


class ApplicationListSerializer(serializers.ModelSerializer):
    opportunity = OpportunityListSerializer(read_only=True)
    job_title = serializers.CharField(source="opportunity.job.title", read_only=True)
    job_company = serializers.CharField(source="opportunity.job.company", read_only=True)
    match_score = serializers.IntegerField(
        source="opportunity.match_score", read_only=True, allow_null=True
    )
    has_tailored_resume = serializers.SerializerMethodField()
    has_cover_letter = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id",
            "opportunity",
            "job_title",
            "job_company",
            "match_score",
            "stage",
            "applied_at",
            "target_follow_up_at",
            "notes",
            "priority",
            "has_tailored_resume",
            "has_cover_letter",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_has_tailored_resume(self, obj: Application) -> bool:
        materials = getattr(obj, "_material_types", None)
        if materials is not None:
            return "tailored_resume" in materials
        return obj.opportunity.application_materials.filter(
            material_type="tailored_resume"
        ).exists()

    def get_has_cover_letter(self, obj: Application) -> bool:
        materials = getattr(obj, "_material_types", None)
        if materials is not None:
            return "cover_letter" in materials
        return obj.opportunity.application_materials.filter(
            material_type="cover_letter"
        ).exists()


class ApplicationDetailSerializer(ApplicationListSerializer):
    stage_events = ApplicationStageEventSerializer(many=True, read_only=True)
    materials = serializers.SerializerMethodField()
    interview_plans = serializers.SerializerMethodField()
    job = JobSerializer(source="opportunity.job", read_only=True)

    class Meta(ApplicationListSerializer.Meta):
        fields = ApplicationListSerializer.Meta.fields + (
            "job",
            "stage_events",
            "materials",
            "interview_plans",
        )

    def get_materials(self, obj: Application) -> list:
        from apps.resumes.repositories import ApplicationMaterialRepository

        user = self.context.get("user")
        if not user:
            return []
        materials = ApplicationMaterialRepository().list_for_opportunity(
            user, obj.opportunity_id
        )
        return ApplicationMaterialSerializer(materials, many=True).data

    def get_interview_plans(self, obj: Application) -> list:
        from apps.applications.repositories import InterviewPlanRepository

        user = self.context.get("user")
        if not user:
            return []
        plans = InterviewPlanRepository().list_for_application(user, obj.id)
        return InterviewPlanListSerializer(plans, many=True).data


class ApplicationUpdateSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=ApplicationStage.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=ApplicationPriority.choices, required=False)
    target_follow_up_at = serializers.DateTimeField(required=False, allow_null=True)
    stage_notes = serializers.CharField(required=False, allow_blank=True, default="")


class ApplicationKanbanSerializer(serializers.Serializer):
    stage_order = serializers.ListField(child=serializers.CharField())
    stages = serializers.DictField(child=ApplicationListSerializer(many=True))


class InterviewPlanListSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    job_title = serializers.CharField(source="opportunity.job.title", read_only=True)
    job_company = serializers.CharField(source="opportunity.job.company", read_only=True)
    application_stage = serializers.CharField(
        source="application.stage", read_only=True, allow_null=True
    )
    opportunity_id = serializers.UUIDField(source="opportunity.id", read_only=True)
    application_id = serializers.UUIDField(
        source="application.id", read_only=True, allow_null=True
    )
    interview_id = serializers.UUIDField(
        source="interview.id", read_only=True, allow_null=True
    )

    class Meta:
        model = InterviewPlan
        fields = (
            "id",
            "type",
            "opportunity_id",
            "application_id",
            "interview_id",
            "job_title",
            "job_company",
            "application_stage",
            "prompt_name",
            "prompt_version",
            "model_name",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_type(self, obj: InterviewPlan) -> str:
        return "prep_plan"


class InterviewPlanDetailSerializer(InterviewPlanListSerializer):
    content = serializers.JSONField()
    markdown = serializers.CharField()
    reasoning_summary = serializers.SerializerMethodField()

    class Meta(InterviewPlanListSerializer.Meta):
        fields = InterviewPlanListSerializer.Meta.fields + (
            "content",
            "markdown",
            "reasoning_summary",
        )

    def get_reasoning_summary(self, obj: InterviewPlan) -> str:
        return (obj.metadata or {}).get("reasoning_summary", "")


class InterviewScheduledListSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    job_title = serializers.CharField(source="opportunity.job.title", read_only=True)
    job_company = serializers.CharField(source="opportunity.job.company", read_only=True)
    opportunity_id = serializers.UUIDField(source="opportunity.id", read_only=True)
    application_id = serializers.UUIDField(
        source="application.id", read_only=True, allow_null=True
    )

    class Meta:
        model = Interview
        fields = (
            "id",
            "type",
            "opportunity_id",
            "application_id",
            "job_title",
            "job_company",
            "scheduled_at",
            "round_label",
            "format",
            "outcome",
            "source",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_type(self, obj: Interview) -> str:
        return "scheduled"


class InterviewDetailSerializer(InterviewScheduledListSerializer):
    interviewer_notes = serializers.CharField()
    job_description = serializers.CharField()

    class Meta(InterviewScheduledListSerializer.Meta):
        fields = InterviewScheduledListSerializer.Meta.fields + (
            "interviewer_notes",
            "job_description",
        )


class InterviewCreateSerializer(serializers.Serializer):
    company = serializers.CharField(max_length=512)
    job_title = serializers.CharField(max_length=512)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    round_label = serializers.CharField(required=False, allow_blank=True, default="")
    format = serializers.ChoiceField(
        choices=InterviewFormat.choices,
        required=False,
        default=InterviewFormat.VIDEO,
    )
    interviewer_notes = serializers.CharField(required=False, allow_blank=True, default="")
    outcome = serializers.ChoiceField(
        choices=InterviewOutcome.choices,
        required=False,
        default=InterviewOutcome.SCHEDULED,
    )
    job_description = serializers.CharField(required=False, allow_blank=True, default="")


class InterviewUpdateSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    round_label = serializers.CharField(required=False, allow_blank=True)
    format = serializers.ChoiceField(choices=InterviewFormat.choices, required=False)
    interviewer_notes = serializers.CharField(required=False, allow_blank=True)
    outcome = serializers.ChoiceField(choices=InterviewOutcome.choices, required=False)
    job_description = serializers.CharField(required=False, allow_blank=True)


class InterviewListResponseSerializer(serializers.Serializer):
    upcoming_interviews = InterviewScheduledListSerializer(many=True)
    active = InterviewPlanListSerializer(many=True)
    upcoming = InterviewPlanListSerializer(many=True)
    recent = InterviewPlanListSerializer(many=True)
