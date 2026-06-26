from django.contrib import admin

from apps.workflows.models import WorkflowExecution


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "user__email")
