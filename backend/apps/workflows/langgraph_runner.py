"""LangGraph root workflow runner for all workflow intents."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from apps.agents.serializers import AgentExecutionSerializer
from apps.workflows.intent import WORKFLOW_INTENT_INTERVIEW_PREP
from apps.workflows.langgraph_nodes import (
    complete_workflow_node,
    fail_workflow_node,
    guided_finalize_node,
    pause_for_user_node,
    planner_node,
    replan_node,
    route_after_guided_finalize,
    route_after_plan,
    route_after_replan,
    route_after_tool_executor,
    tool_executor_node,
)
from apps.workflows.langgraph_state import WorkflowGraphState
from apps.workflows.serializers import WorkflowExecutionSerializer


def build_workflow_graph():
    """Compile the root LangGraph with planner entry and intent-specific routing."""
    builder = StateGraph(WorkflowGraphState)
    builder.add_node("planner", planner_node)
    builder.add_node("tool_executor", tool_executor_node)
    builder.add_node("replan", replan_node)
    builder.add_node("guided_finalize", guided_finalize_node)
    builder.add_node("pause_for_user", pause_for_user_node)
    builder.add_node("complete", complete_workflow_node)
    builder.add_node("fail", fail_workflow_node)

    builder.set_entry_point("planner")
    builder.add_conditional_edges("planner", route_after_plan)
    builder.add_conditional_edges("tool_executor", route_after_tool_executor)
    builder.add_conditional_edges("replan", route_after_replan)
    builder.add_conditional_edges("guided_finalize", route_after_guided_finalize)
    builder.add_edge("pause_for_user", "complete")
    builder.add_edge("complete", END)
    builder.add_edge("fail", END)

    return builder.compile()


class LangGraphWorkflowRunner:
    def __init__(self, graph=None):
        self.graph = graph or build_workflow_graph()

    def run(self, service, user, workflow, goal: str) -> dict:
        """Run the workflow graph and return the legacy executor response shape."""
        config = {
            "configurable": {
                "service": service,
                "user": user,
                "workflow": workflow,
                "runtime": {
                    "job_search_execution": None,
                    "evaluation_executions": [],
                    "interview_prep_execution": None,
                },
            }
        }

        initial_state: WorkflowGraphState = {"goal": goal}

        final_state = self.graph.invoke(initial_state, config=config)

        if final_state.get("failed"):
            raise RuntimeError(final_state.get("error_message") or "Workflow failed.")

        return self._build_response(service, user, workflow, config, final_state)

    def _build_response(
        self,
        service,
        user,
        workflow,
        config: dict,
        final_state: WorkflowGraphState,
    ) -> dict:
        workflow.refresh_from_db()
        result = workflow.result or {}
        cfg = config.get("configurable") or {}
        plan_result = cfg.get("plan_result") or final_state.get("plan_result") or {}
        runtime = cfg.get("runtime") or {}

        workflow_intent = result.get("workflow_intent") or final_state.get("workflow_intent", "")
        planned_agents = result.get("planned_agents") or final_state.get("planned_agents", [])
        job_search_execution = runtime.get("job_search_execution")
        evaluation_executions = runtime.get("evaluation_executions") or []
        interview_prep_execution = runtime.get("interview_prep_execution")

        planner_execution = plan_result.get("execution")
        response: dict = {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "plan_summary": plan_result.get("plan_summary", result.get("plan_summary", "")),
            "suggested_steps": plan_result.get("suggested_steps", result.get("suggested_steps", [])),
            "workflow_intent": workflow_intent,
            "planned_agents": planned_agents,
            "completed_agents": result.get("completed_agents", []),
            "discovered_count": result.get("discovered_count", 0),
            "provider_summary": result.get("provider_summary", {"providers": {}}),
            "job_search_summary": result.get("job_search_summary", ""),
            "evaluated_count": result.get("evaluated_count", 0),
            "accepted_count": result.get("accepted_count", 0),
            "borderline_count": result.get("borderline_count", 0),
            "rejected_count": result.get("rejected_count", 0),
            "top_match_score": result.get("top_match_score", 0),
            "evaluation_executions": evaluation_executions,
            "constraints": result.get("constraints", {}),
            "tool_plan": result.get("tool_plan", []),
            "success_criteria": result.get("success_criteria", []),
            "user_visible_plan": result.get("user_visible_plan", ""),
            "plan_history": result.get("plan_history", []),
            "replan_events": result.get("replan_events", []),
            "next_action": result.get("next_action", ""),
        }

        if planner_execution is not None:
            response["planner_execution"] = AgentExecutionSerializer(planner_execution).data

        if job_search_execution is not None:
            response["job_search_execution"] = AgentExecutionSerializer(
                job_search_execution
            ).data

        if interview_prep_execution is not None:
            response["interview_prep_execution"] = AgentExecutionSerializer(
                interview_prep_execution
            ).data

        if workflow_intent == WORKFLOW_INTENT_INTERVIEW_PREP:
            response.update(
                {
                    "selected_opportunity_id": result.get("selected_opportunity_id"),
                    "interview_plan_id": result.get("interview_plan_id"),
                    "interview_prep_target_source": result.get("interview_prep_target_source"),
                    "reasoning_summary": result.get("reasoning_summary", ""),
                }
            )

        if result.get("tailor_options") is not None:
            response["tailor_options"] = result.get("tailor_options")
        if result.get("tailor_selection_pending"):
            response["tailor_selection_pending"] = result.get("tailor_selection_pending")

        for key in (
            "existing_opportunity_count",
            "high_match_count",
            "saved_count",
            "recommended_opportunity_ids",
        ):
            if key in result:
                response[key] = result[key]

        return response
