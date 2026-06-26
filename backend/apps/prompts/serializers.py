from rest_framework import serializers

from apps.prompts.models import PromptVersion


class PromptVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptVersion
        fields = (
            "id",
            "name",
            "version",
            "template",
            "variables",
            "is_active",
            "description",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
