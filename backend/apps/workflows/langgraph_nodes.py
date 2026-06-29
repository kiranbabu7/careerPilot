"""LangGraph nodes wrapping planner, tool registry, and replan logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.workflows.intent import (
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_CONVERSATIONAL,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    build_intent_classification,
    build_planned_agents,
    classify_workflow_intent,
)
from apps.workflows.langgraph_state import (
    WorkflowGraphState,
    pop_next_tool,
    safe_tool_result_payload,
)
from apps.workflows.models import WorkflowExecutionStatus
from apps.workflows.tool_registry import ToolResult

if TYPE_CHECKING:
    from apps.workflows.services import WorkflowService

GUIDED_INTENTS = frozenset(
    {
        WORKFLOW_INTENT_TAILOR_RESUME,
        WORKFLOW_INTENT_COVER_LETTER,
        WORKFLOW_INTENT_APPLICATION_TRACKING,
        WORKFLOW_INTENT_CONVERSATIONAL,
    }
)


def _graph_config(config: dict) -> dict[str, Any]:
    return config.get("configurable") or {}


def _graph_runtime(config: dict) -> dict[str, Any]:
    cfg = _graph_config(config)
    runtime = cfg.get("runtime")
    if runtime is None:
        runtime = {
            "job_search_execution": None,
            "evaluation_executions": [],
            "interview_prep_execution": None,
        }
        cfg["runtime"] = runtime
    return runtime


def planner_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Run PlannerAgent.plan() and initialize workflow graph state."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    user = cfg["user"]
    workflow = cfg["workflow"]
    goal = state["goal"]
    existing_result = workflow.result or {}

    workflow_intent = classify_workflow_intent(goal)
    intent_classification = existing_result.get("intent_classification") or build_intent_classification(goal)
    planned_agents = build_planned_agents(workflow_intent)

    plan_result = service.planner.plan(
        user, workflow, goal, workflow_intent=workflow_intent
    )
    cfg["plan_result"] = plan_result

    workflow_intent = plan_result.get("workflow_intent") or workflow_intent
    planned_agents = plan_result.get("planned_agents") or planned_agents
    context = dict(plan_result["context"])
    tool_plan = list(plan_result.get("tool_plan") or [])
    constraints = plan_result.get("constraints") or {}
    plan_history = [
        {
            "phase": "initial",
            "tool_plan": tool_plan,
            "constraints": constraints,
            "at": timezone.now().isoformat(),
        }
    ]

    workflow.context = {
        **context,
        "workflow_intent": workflow_intent,
        "planned_agents": planned_agents,
    }
    workflow.result = {
        **existing_result,
        "plan_summary": plan_result["plan_summary"],
        "suggested_steps": plan_result["suggested_steps"],
        "workflow_intent": workflow_intent,
        "intent_classification": intent_classification,
        "planned_agents": planned_agents,
        "completed_agents": ["planner"],
        "constraints": constraints,
        "tool_plan": tool_plan,
        "success_criteria": plan_result.get("success_criteria", []),
        "user_visible_plan": plan_result.get("user_visible_plan", ""),
        "reasoning_summary": service._planner_reasoning_summary(plan_result),
        "plan_history": plan_history,
        "replan_events": [],
        "requires_confirmation": plan_result.get("requires_confirmation", False),
        "tool_results": [],
    }
    workflow.save(update_fields=["context", "result", "updated_at"])

    return {
        "workflow_intent": workflow_intent,
        "planned_agents": planned_agents,
        "intent_classification": intent_classification,
        "context": context,
        "tool_queue": list(tool_plan),
        "plan_history": plan_history,
        "replan_events": [],
        "stopped_for_user": False,
        "stop_message": "",
        "failed": False,
        "error_message": "",
        "plan_result": plan_result,
    }


def tool_executor_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Execute the next tool from the queue via WorkflowToolRegistry."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    user = cfg["user"]
    workflow = cfg["workflow"]
    registry = service._get_tool_registry()
    context = state.get("context") or cfg.get("context") or {}
    tool_queue = list(state.get("tool_queue") or [])

    while tool_queue:
        step, tool_queue = pop_next_tool(tool_queue)
        tool_key = step.get("tool", "")
        tool_def = registry.get(tool_key)
        if tool_def is None:
            continue

        if not step.get("auto_run", tool_def.auto_run) and tool_def.requires_confirmation:
            stop_message = step.get("reason") or tool_def.description
            registry.merge_result(
                workflow,
                tool_key,
                ToolResult(
                    tool=tool_key,
                    success=True,
                    summary="Waiting for user confirmation.",
                    requires_user=True,
                    user_message=stop_message,
                ),
            )
            return {
                "tool_queue": tool_queue,
                "current_step": step,
                "last_tool_key": tool_key,
                "stopped_for_user": True,
                "stop_message": stop_message,
            }

        tool_result = registry.execute(
            user, workflow, tool_key, context, params=step.get("params") or {}
        )
        registry.merge_result(workflow, tool_key, tool_result)

        runtime = _graph_runtime(config)

        update: WorkflowGraphState = {
            "tool_queue": tool_queue,
            "current_step": step,
            "last_tool_key": tool_key,
            "last_tool_result": safe_tool_result_payload(tool_key, tool_result),
        }

        if tool_key == "job_search" and tool_result.execution is not None:
            runtime["job_search_execution"] = tool_result.execution
        if tool_key == "job_evaluation":
            runtime["evaluation_executions"] = tool_result.data.get(
                "evaluation_executions", []
            )
        if tool_key == "interview_prep" and tool_result.execution is not None:
            runtime["interview_prep_execution"] = tool_result.execution

        agent_name = registry.agent_name_for(tool_key)
        if agent_name not in ("ask_user",):
            service._append_completed_agent(workflow, agent_name)

        if tool_result.requires_user:
            update["stopped_for_user"] = True
            update["stop_message"] = tool_result.user_message or state.get("stop_message", "")
            return update

        return update

    return {"tool_queue": tool_queue, "last_tool_key": ""}


def rerun_tool_executor_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Execute all rerun pipeline tools without replan."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    user = cfg["user"]
    workflow = cfg["workflow"]
    registry = service._get_tool_registry()
    context = cfg.get("context") or state.get("context") or {}
    tool_queue = list(state.get("tool_queue") or [])
    runtime = _graph_runtime(config)

    while tool_queue:
        step, tool_queue = pop_next_tool(tool_queue)
        tool_key = step.get("tool", "")
        tool_def = registry.get(tool_key)
        if tool_def is None:
            continue

        tool_result = registry.execute(
            user, workflow, tool_key, context, params=step.get("params") or {}
        )
        registry.merge_result(workflow, tool_key, tool_result)

        agent_name = registry.agent_name_for(tool_key)
        if agent_name not in ("ask_user",):
            service._append_completed_agent(workflow, agent_name)

        if tool_key == "job_search" and tool_result.execution is not None:
            runtime["job_search_execution"] = tool_result.execution
        if tool_key == "job_evaluation":
            runtime["evaluation_executions"] = tool_result.data.get(
                "evaluation_executions", []
            )

    return {"tool_queue": tool_queue}


def replan_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Call planner replan and mutate tool queue based on the outcome."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    user = cfg["user"]
    workflow = cfg["workflow"]
    goal = state["goal"]
    context = state.get("context") or {}
    tool_key = state.get("last_tool_key", "")
    tool_queue = list(state.get("tool_queue") or [])
    plan_history = list(state.get("plan_history") or [])
    replan_events = list(state.get("replan_events") or [])

    workflow.refresh_from_db()
    safe_tool_result = state.get("last_tool_result") or {}
    replan_outcome = service.planner.replan(
        user,
        workflow,
        goal,
        context=context,
        last_tool_result=safe_tool_result,
        pending_tools=tool_queue,
    )

    replan_event = {
        "action": replan_outcome["action"],
        "reason": replan_outcome["reason"],
        "message": replan_outcome.get("message", ""),
        "after_tool": tool_key,
        "at": timezone.now().isoformat(),
    }
    replan_events.append(replan_event)
    workflow.result = {
        **(workflow.result or {}),
        "replan_events": replan_events,
    }
    workflow.save(update_fields=["result", "updated_at"])

    action = replan_outcome["action"]
    update: WorkflowGraphState = {
        "replan_events": replan_events,
        "replan_action": action,
    }

    if action == "complete":
        if replan_outcome.get("message"):
            update["stop_message"] = replan_outcome["message"]
        return update

    if action == "fail_with_reason":
        update["failed"] = True
        update["error_message"] = replan_outcome.get("message") or replan_outcome["reason"]
        return update

    if action == "ask_user":
        update["stopped_for_user"] = True
        update["stop_message"] = replan_outcome.get("message") or replan_outcome["reason"]
        return update

    if action == "insert_tools":
        inserted = replan_outcome.get("tools_to_insert") or []
        tool_queue = inserted + tool_queue
        plan_history.append(
            {
                "phase": "replan_insert",
                "tool_plan": inserted,
                "reason": replan_outcome["reason"],
                "at": timezone.now().isoformat(),
            }
        )
        workflow.result = {
            **(workflow.result or {}),
            "plan_history": plan_history,
            "tool_plan": (workflow.result.get("tool_plan") or []) + inserted,
        }
        workflow.save(update_fields=["result", "updated_at"])
        update["tool_queue"] = tool_queue
        update["plan_history"] = plan_history
    elif action == "skip_tool" and tool_queue:
        _, tool_queue = pop_next_tool(tool_queue)
        update["tool_queue"] = tool_queue

    return update


def guided_finalize_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Finalize guided workflows with opportunity summary and tailor options."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    user = cfg["user"]
    workflow = cfg["workflow"]
    workflow_intent = state.get("workflow_intent", "")
    plan_result = cfg.get("plan_result") or {}

    opportunity_summary = service._summarize_existing_opportunities(user)
    if workflow_intent == WORKFLOW_INTENT_CONVERSATIONAL:
        from apps.workflows.follow_up import build_help_reply

        intent_classification = (workflow.result or {}).get("intent_classification") or {}
        variant = intent_classification.get("conversational_variant", "help")
        next_action = build_help_reply(workflow, variant=variant)
    else:
        next_action = service._next_action_for_intent(workflow_intent, opportunity_summary)

    planned_agents = plan_result.get("planned_agents") or build_planned_agents(workflow_intent)
    completed_agents = list((workflow.result or {}).get("completed_agents") or planned_agents)
    tailor_options = None
    tailor_selection_pending = False

    if workflow_intent == WORKFLOW_INTENT_TAILOR_RESUME:
        tailor_options = service._build_tailor_options_payload(user, workflow.goal or "")
        tailor_selection_pending = True

    result_update = {
        **(workflow.result or {}),
        "workflow_intent": workflow_intent,
        "planned_agents": planned_agents,
        "completed_agents": completed_agents,
        "next_action": next_action,
        **opportunity_summary,
    }
    if tailor_options is not None:
        result_update["tailor_options"] = tailor_options
        result_update["tailor_selection_pending"] = tailor_selection_pending

    workflow.result = result_update
    workflow.save(update_fields=["result", "updated_at"])

    return {"stop_message": next_action, "stopped_for_user": bool(state.get("stopped_for_user"))}


def pause_for_user_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Record user-confirmation pause before final completion."""
    cfg = _graph_config(config)
    workflow = cfg["workflow"]
    stop_message = state.get("stop_message") or ""

    workflow.refresh_from_db()
    result = workflow.result or {}
    if stop_message and not str(result.get("next_action") or "").strip():
        result["next_action"] = stop_message
    workflow.result = result
    workflow.save(update_fields=["result", "updated_at"])

    return {"stopped_for_user": True, "stop_message": stop_message}


def complete_workflow_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Finalize a successful workflow run."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    user = cfg["user"]
    workflow = cfg["workflow"]
    plan_result = cfg.get("plan_result") or {}
    stop_message = state.get("stop_message") or ""
    workflow_intent = state.get("workflow_intent", "")

    workflow.refresh_from_db()
    result = workflow.result or {}
    if state.get("stopped_for_user") and stop_message and not str(result.get("next_action") or "").strip():
        result["next_action"] = stop_message
    elif not result.get("next_action"):
        if workflow_intent == WORKFLOW_INTENT_INTERVIEW_PREP:
            result["next_action"] = stop_message or ""
        elif workflow_intent != WORKFLOW_INTENT_CONVERSATIONAL:
            result["next_action"] = (
                "Review discovered opportunities and saved matches in your workspace."
            )
    workflow.result = result
    workflow.status = WorkflowExecutionStatus.COMPLETED
    workflow.completed_at = timezone.now()
    workflow.save()

    plan_summary = plan_result.get("plan_summary") or result.get("plan_summary", "")
    if plan_summary:
        service.activity_service.record_workflow_started(user, workflow)
        service.memory_service.record_workflow_context(user, workflow, plan_summary)
    service._seed_welcome_chat_message(user, workflow)

    return {}


def rerun_complete_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Finalize a search rerun."""
    cfg = _graph_config(config)
    service: WorkflowService = cfg["service"]
    workflow = cfg["workflow"]
    overrides = cfg.get("overrides") or {}

    workflow.refresh_from_db()
    existing_result = workflow.result or {}
    rerun_history = list(existing_result.get("search_rerun_history") or [])
    rerun_history.append(
        {
            "overrides": overrides,
            "discovered_count": existing_result.get("discovered_count", 0),
            "at": timezone.now().isoformat(),
        }
    )
    workflow.result = {
        **existing_result,
        "search_rerun_history": rerun_history,
        "last_search_overrides": overrides,
        "search_rerun_in_progress": False,
        "next_action": "",
    }
    workflow.status = WorkflowExecutionStatus.COMPLETED
    workflow.completed_at = timezone.now()
    workflow.save()

    return {}


def fail_workflow_node(state: WorkflowGraphState, config: dict) -> WorkflowGraphState:
    """Mark workflow failed."""
    cfg = _graph_config(config)
    workflow = cfg["workflow"]
    error_message = state.get("error_message") or "Workflow failed during replanning."

    workflow.status = WorkflowExecutionStatus.FAILED
    workflow.error_message = error_message
    workflow.completed_at = timezone.now()
    workflow.save()

    return {"failed": True, "error_message": error_message}


def route_after_plan(state: WorkflowGraphState) -> str:
    if state.get("tool_queue"):
        return "tool_executor"
    intent = state.get("workflow_intent", "")
    if intent in GUIDED_INTENTS:
        return "guided_finalize"
    return "complete"


def route_after_tool_executor(state: WorkflowGraphState) -> str:
    intent = state.get("workflow_intent", "")

    if state.get("stopped_for_user"):
        if intent in GUIDED_INTENTS:
            return "guided_finalize"
        return "pause_for_user"

    if intent in GUIDED_INTENTS:
        if state.get("tool_queue"):
            return "tool_executor"
        return "guided_finalize"

    if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        if state.get("tool_queue"):
            return "tool_executor"
        return "complete"

    if state.get("last_tool_key"):
        return "replan"
    if state.get("tool_queue"):
        return "tool_executor"
    return "complete"


def route_after_simple_tool_executor(state: WorkflowGraphState) -> str:
    if state.get("stopped_for_user"):
        return "pause_for_user"
    if state.get("tool_queue"):
        return "tool_executor"
    return "complete"


def route_after_guided_finalize(state: WorkflowGraphState) -> str:
    if state.get("stopped_for_user"):
        return "pause_for_user"
    return "complete"


def route_after_guided_tool_executor(state: WorkflowGraphState) -> str:
    if state.get("stopped_for_user"):
        return "guided_finalize"
    if state.get("tool_queue"):
        return "tool_executor"
    return "guided_finalize"


def route_after_replan(state: WorkflowGraphState) -> str:
    if state.get("failed"):
        return "fail"
    action = state.get("replan_action", "")
    if action == "ask_user" or state.get("stopped_for_user"):
        return "pause_for_user"
    if action == "complete":
        return "complete"
    if state.get("tool_queue"):
        return "tool_executor"
    return "complete"
