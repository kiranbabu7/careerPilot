from rest_framework import serializers

from apps.resumes.models import ApplicationMaterial, Resume, ResumeAnalysis
from apps.resumes.resume_content import content_to_preview_text


class ResumeAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumeAnalysis
        fields = (
            "id",
            "model_name",
            "raw_summary",
            "health_score",
            "ats_score",
            "strengths",
            "weaknesses",
            "missing_keywords",
            "improvement_suggestions",
            "extracted_skills",
            "created_at",
        )
        read_only_fields = fields


class ResumeSerializer(serializers.ModelSerializer):
    latest_analysis = ResumeAnalysisSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Resume
        fields = (
            "id",
            "original_filename",
            "content_type",
            "file_size",
            "extracted_text",
            "is_active",
            "latest_analysis",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ResumeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class ResumeListItemSerializer(serializers.Serializer):
    def to_representation(self, instance):
        resume = instance["resume"]
        analysis = instance.get("latest_analysis")
        data = ResumeSerializer(resume).data
        if analysis:
            data["latest_analysis"] = ResumeAnalysisSerializer(analysis).data
        else:
            data["latest_analysis"] = None
        return data


class ApplicationMaterialSerializer(serializers.ModelSerializer):
    opportunity_title = serializers.SerializerMethodField()
    opportunity_company = serializers.SerializerMethodField()
    source_resume_filename = serializers.SerializerMethodField()
    content_preview = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationMaterial
        fields = (
            "id",
            "opportunity",
            "opportunity_title",
            "opportunity_company",
            "source_resume",
            "source_resume_filename",
            "material_type",
            "content",
            "content_preview",
            "prompt_name",
            "prompt_version",
            "model_name",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_content_preview(self, obj) -> str:
        return content_to_preview_text(obj.content)

    def get_opportunity_title(self, obj) -> str:
        return obj.opportunity.job.title

    def get_opportunity_company(self, obj) -> str:
        return obj.opportunity.job.company

    def get_source_resume_filename(self, obj) -> str:
        return obj.source_resume.original_filename
