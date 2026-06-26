from django.contrib import admin

from apps.agents.models import AgentExecution


@admin.register(AgentExecution)
class AgentExecutionAdmin(admin.ModelAdmin):
    list_display = ("agent_name", "user", "status", "created_at")
    list_filter = ("status", "agent_name")
    search_fields = ("agent_name", "user__email")
