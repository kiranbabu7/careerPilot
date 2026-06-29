"""Workflow execution timeline — Phase 8."""

from apps.agents.agent_labels import agent_label, duration_ms
from apps.agents.models import AgentExecutionStatus
from apps.applications.models import ApplicationStageEvent
from apps.memory.models import ActivityEvent


class WorkflowTimelineService:
    def build_timeline(self, workflow) -> list[dict]:
        items: list[dict] = []

        if workflow.started_at:
            items.append(
                {
                    "id": f"workflow-{workflow.id}-started",
                    "item_type": "workflow_started",
                    "timestamp": workflow.started_at.isoformat(),
                    "title": "Workflow started",
                    "description": workflow.goal or workflow.name,
                    "workflow_id": str(workflow.id),
                    "status": workflow.status,
                    "metadata": {"status": workflow.status},
                }
            )

        for execution in workflow.agent_executions.order_by("started_at", "created_at"):
            base = {
                "workflow_id": str(workflow.id),
                "agent_execution_id": str(execution.id),
                "agent_name": execution.agent_name,
                "agent_label": agent_label(execution.agent_name),
                "status": execution.status,
                "duration_ms": duration_ms(execution.started_at, execution.completed_at),
                "metadata": {
                    "reasoning_summary": execution.reasoning_summary,
                    "error_message": execution.error_message,
                },
            }
            started_ts = execution.started_at or execution.created_at
            if started_ts:
                summary = execution.reasoning_summary or ""
                items.append(
                    {
                        **base,
                        "id": f"agent-{execution.id}-started",
                        "item_type": "agent_started",
                        "timestamp": started_ts.isoformat(),
                        "title": f"{agent_label(execution.agent_name)} started",
                        "description": summary[:200] if summary else "",
                        "metadata": {
                            **base["metadata"],
                            "full_description": summary,
                        },
                    }
                )

            completed_ts = execution.completed_at
            if completed_ts:
                if execution.status == AgentExecutionStatus.FAILED:
                    item_type = "agent_failed"
                    title = f"{agent_label(execution.agent_name)} failed"
                else:
                    item_type = "agent_completed"
                    title = f"{agent_label(execution.agent_name)} completed"
                summary = execution.reasoning_summary or ""
                error_msg = execution.error_message or ""
                full_description = summary or error_msg
                items.append(
                    {
                        **base,
                        "id": f"agent-{execution.id}-completed",
                        "item_type": item_type,
                        "timestamp": completed_ts.isoformat(),
                        "title": title,
                        "description": full_description[:200] if full_description else "",
                        "metadata": {
                            **base["metadata"],
                            "full_description": full_description,
                        },
                    }
                )

        workflow_id = str(workflow.id)
        activity_events = ActivityEvent.objects.filter(
            user=workflow.user,
            metadata__workflow_id=workflow_id,
        ).order_by("created_at")

        for event in activity_events:
            if event.event_type == ActivityEvent.EventType.APPLICATION_STAGE_CHANGED:
                item_type = "application_stage_changed"
            elif event.event_type == ActivityEvent.EventType.INTERVIEW_PREP_GENERATED:
                item_type = "interview_prep_generated"
            elif event.event_type == ActivityEvent.EventType.APPLICATION_CREATED:
                item_type = "application_created"
            elif event.event_type == ActivityEvent.EventType.DECISION_GENERATED:
                item_type = "decision_generated"
            else:
                continue

            items.append(
                {
                    "id": f"activity-{event.id}",
                    "item_type": item_type,
                    "timestamp": event.created_at.isoformat(),
                    "title": event.title,
                    "description": event.description,
                    "workflow_id": workflow_id,
                    "metadata": event.metadata,
                }
            )

        opportunity_ids = list(
            workflow.opportunities.values_list("id", flat=True)
        )
        if opportunity_ids:
            stage_events = (
                ApplicationStageEvent.objects.filter(
                    application__user=workflow.user,
                    application__opportunity_id__in=opportunity_ids,
                )
                .select_related("application", "application__opportunity__job")
                .order_by("created_at")
            )
            for stage_event in stage_events:
                job = stage_event.application.opportunity.job
                items.append(
                    {
                        "id": f"stage-{stage_event.id}",
                        "item_type": "application_stage_changed",
                        "timestamp": stage_event.created_at.isoformat(),
                        "title": "Application stage updated",
                        "description": (
                            f"{job.title}: {stage_event.from_stage} → {stage_event.to_stage}"
                        ),
                        "workflow_id": workflow_id,
                        "metadata": {
                            "application_id": str(stage_event.application_id),
                            "opportunity_id": str(stage_event.application.opportunity_id),
                            "from_stage": stage_event.from_stage,
                            "to_stage": stage_event.to_stage,
                        },
                    }
                )

        if workflow.completed_at and workflow.status in ("completed", "failed"):
            items.append(
                {
                    "id": f"workflow-{workflow.id}-completed",
                    "item_type": "workflow_completed"
                    if workflow.status == "completed"
                    else "workflow_failed",
                    "timestamp": workflow.completed_at.isoformat(),
                    "title": f"Workflow {workflow.status}",
                    "description": workflow.error_message or workflow.name,
                    "workflow_id": workflow_id,
                    "status": workflow.status,
                    "metadata": {"status": workflow.status},
                }
            )

        items.sort(key=lambda item: item["timestamp"])
        return items
