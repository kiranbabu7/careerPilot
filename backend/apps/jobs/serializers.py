from rest_framework import serializers

from apps.jobs.models import Job, Opportunity, OpportunityStatus


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = (
            "id",
            "external_id",
            "source",
            "title",
            "company",
            "location",
            "is_remote",
            "salary_min",
            "salary_max",
            "salary_currency",
            "description",
            "apply_url",
            "posted_at",
            "company_research",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OpportunitySerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "job",
            "workflow_execution",
            "status",
            "source_agent",
            "match_context",
            "match_score",
            "evaluation",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OpportunityListSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "job",
            "status",
            "source_agent",
            "match_context",
            "match_score",
            "evaluation",
            "created_at",
        )
        read_only_fields = fields


class OpportunityStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OpportunityStatus.choices)
