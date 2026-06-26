from rest_framework import serializers

from apps.resumes.models import Resume, ResumeAnalysis


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
