"""Workflow tool registry — maps planner tools to existing agents and services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from apps.agents.company_research import COMPANY_RESEARCH_AGENT_NAME, CompanyResearchAgent
from apps.agents.decision import DECISION_AGENT_NAME, DecisionAgent
from apps.agents.interview_prep import INTERVIEW_PREP_AGENT_NAME
from apps.agents.planner_provider import TOOL_TO_AGENT
from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD
from apps.jobs.models import OpportunityStatus

if TYPE_CHECKING:
    from apps.workflows.services import WorkflowService


@dataclass
class ToolResult:
    tool: str
    success: bool
    summary: str
    data: dict = field(default_factory=dict)
    execution: Any = None
    requires_user: bool = False
    user_message: str = ""


@dataclass
class ToolDefinition:
    key: str
    agent_name: str
    description: str
    auto_run: bool
    requires_confirmation: bool
    handler: Callable[..., ToolResult]


class WorkflowToolRegistry:
    """Registry of callable workflow tools for the agentic executor."""

    def __init__(self, service: WorkflowService):
        self.service = service
        self._tools = self._build_tools()

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get(self, tool_key: str) -> ToolDefinition | None:
        return self._tools.get(tool_key)

    def agent_name_for(self, tool_key: str) -> str:
        return TOOL_TO_AGENT.get(tool_key, tool_key)

    def execute(
        self,
        user,
        workflow,
        tool_key: str,
        context: dict,
        *,
        params: dict | None = None,
    ) -> ToolResult:
        tool = self.get(tool_key)
        if tool is None:
            return ToolResult(
                tool=tool_key,
                success=False,
                summary=f"Unknown tool: {tool_key}",
            )
        return tool.handler(user, workflow, context, params or {})

    def merge_result(self, workflow, tool_key: str, tool_result: ToolResult) -> None:
        result = dict(workflow.result or {})
        tool_results = list(result.get("tool_results") or [])
        tool_results.append(
            {
                "tool": tool_key,
                "success": tool_result.success,
                "summary": tool_result.summary,
                "data": {
                    k: v
                    for k, v in tool_result.data.items()
                    if k not in ("evaluation_executions",)
                },
            }
        )
        result["tool_results"] = tool_results
        result.update(tool_result.data)
        workflow.result = self.service._sanitize_workflow_result(result)

    def _build_tools(self) -> dict[str, ToolDefinition]:
        return {
            "job_search": ToolDefinition(
                key="job_search",
                agent_name="job_search",
                description="Search job boards for matching listings.",
                auto_run=True,
                requires_confirmation=False,
                handler=self._run_job_search,
            ),
            "job_evaluation": ToolDefinition(
                key="job_evaluation",
                agent_name="job_evaluation",
                description="Evaluate discovered opportunities for match score.",
                auto_run=True,
                requires_confirmation=False,
                handler=self._run_job_evaluation,
            ),
            "company_research": ToolDefinition(
                key="company_research",
                agent_name=COMPANY_RESEARCH_AGENT_NAME,
                description=(
                    "Research companies for viable workflow opportunities "
                    f"(match_score >= {BORDERLINE_MATCH_THRESHOLD}, not rejected)."
                ),
                auto_run=True,
                requires_confirmation=False,
                handler=self._run_company_research,
            ),
            "interview_prep": ToolDefinition(
                key="interview_prep",
                agent_name=INTERVIEW_PREP_AGENT_NAME,
                description="Generate interview prep plan.",
                auto_run=True,
                requires_confirmation=False,
                handler=self._run_interview_prep,
            ),
            "resume_tailor": ToolDefinition(
                key="resume_tailor",
                agent_name="resume_tailor",
                description="Tailor resume for a selected role.",
                auto_run=False,
                requires_confirmation=True,
                handler=self._run_resume_tailor,
            ),
            "cover_letter": ToolDefinition(
                key="cover_letter",
                agent_name="cover_letter",
                description="Generate cover letter for a selected opportunity.",
                auto_run=False,
                requires_confirmation=True,
                handler=self._run_cover_letter,
            ),
            "decision": ToolDefinition(
                key="decision",
                agent_name=DECISION_AGENT_NAME,
                description="Synthesize next-action recommendations.",
                auto_run=True,
                requires_confirmation=False,
                handler=self._run_decision,
            ),
            "list_applications": ToolDefinition(
                key="list_applications",
                agent_name="list_applications",
                description="Summarize tracked applications.",
                auto_run=True,
                requires_confirmation=False,
                handler=self._run_list_applications,
            ),
            "add_interview": ToolDefinition(
                key="add_interview",
                agent_name="add_interview",
                description="Schedule an interview record.",
                auto_run=False,
                requires_confirmation=True,
                handler=self._run_add_interview,
            ),
            "ask_user": ToolDefinition(
                key="ask_user",
                agent_name="ask_user",
                description="Pause for user input or confirmation.",
                auto_run=False,
                requires_confirmation=True,
                handler=self._run_ask_user,
            ),
        }

    def _run_job_search(self, user, workflow, context, params) -> ToolResult:
        search_context = dict(context)
        if params.get("broaden"):
            search_context = self.service._broaden_search_context(search_context)
            workflow.result = {
                **(workflow.result or {}),
                "search_broadened": True,
            }
            workflow.save(update_fields=["result", "updated_at"])

        agent = self.service.job_search_agent
        outcome = agent.search(user, workflow, search_context)
        return ToolResult(
            tool="job_search",
            success=outcome["discovered_count"] > 0 or not outcome.get("errors"),
            summary=outcome["reasoning_summary"],
            data={
                "discovered_count": outcome["discovered_count"],
                "provider_summary": outcome["provider_summary"],
                "job_search_summary": outcome["reasoning_summary"],
            },
            execution=outcome["execution"],
        )

    def _run_job_evaluation(self, user, workflow, context, _params) -> ToolResult:
        summary = self.service._evaluate_discovered_opportunities(user, workflow, context)
        return ToolResult(
            tool="job_evaluation",
            success=summary["evaluated_count"] >= 0,
            summary=(
                f"Evaluated {summary['evaluated_count']} roles; "
                f"{summary['accepted_count']} strong matches."
            ),
            data={
                "evaluated_count": summary["evaluated_count"],
                "accepted_count": summary["accepted_count"],
                "borderline_count": summary["borderline_count"],
                "rejected_count": summary["rejected_count"],
                "top_match_score": summary["top_match_score"],
                "evaluation_executions": summary["evaluation_executions"],
            },
        )

    def _run_company_research(self, user, workflow, context, _params) -> ToolResult:
        from apps.workflows.tool_progress import (
            append_tool_progress_event,
            complete_tool_progress,
            start_tool_progress,
            update_tool_progress_label,
        )

        opportunities = self.service.opportunity_repo.list_for_workflow(workflow)
        viable = []
        skipped = 0
        for opportunity in opportunities:
            job = opportunity.job
            research = job.company_research or {}
            if research.get("available"):
                continue
            if opportunity.match_score is None:
                skipped += 1
                continue
            if opportunity.match_score < BORDERLINE_MATCH_THRESHOLD:
                skipped += 1
                continue
            if opportunity.status == OpportunityStatus.REJECTED:
                skipped += 1
                continue
            viable.append(opportunity)

        agent = CompanyResearchAgent()
        researched = 0
        batch_execution = None

        if viable:
            start_tool_progress(
                workflow,
                tool="company_research",
                total=len(viable),
            )

        def _on_progress(opportunity, outcome):
            nonlocal researched
            job = opportunity.job
            update_tool_progress_label(
                workflow,
                current_label=job.company,
            )
            researched += 1
            research = outcome.get("company_research") or {}
            append_tool_progress_event(
                workflow,
                {
                    "kind": "company_research",
                    "company": job.company,
                    "job_title": job.title,
                    "available": research.get("available", False),
                    "summary": (research.get("summary") or "")[:200],
                },
            )
            workflow.refresh_from_db()
            result = dict(workflow.result or {})
            result["companies_researched"] = researched
            workflow.result = result
            workflow.save(update_fields=["result", "updated_at"])

        try:
            if viable:
                batch = agent.research_batch(
                    user,
                    viable,
                    workflow=workflow,
                    on_progress=_on_progress,
                )
                batch_execution = batch.get("execution")
                researched = batch["researched_count"]
        finally:
            if viable:
                complete_tool_progress(workflow, tool="company_research")

        if researched:
            summary = (
                f"Researched {researched} companies for roles that passed "
                f"the match threshold (>= {BORDERLINE_MATCH_THRESHOLD})."
            )
        elif skipped:
            summary = (
                f"Skipped company research for {skipped} role(s) below the match "
                f"threshold or not yet evaluated."
            )
        else:
            summary = "All viable companies already have research."
        return ToolResult(
            tool="company_research",
            success=True,
            summary=summary,
            data={"companies_researched": researched},
            execution=batch_execution,
        )

    def _run_interview_prep(self, user, workflow, context, _params) -> ToolResult:
        goal = context.get("goal") or workflow.goal or ""
        return self.service._execute_interview_prep_tool(user, workflow, goal=goal)

    def _run_resume_tailor(self, user, workflow, context, params) -> ToolResult:
        return ToolResult(
            tool="resume_tailor",
            success=False,
            summary="Resume tailoring requires user confirmation.",
            requires_user=True,
            user_message=params.get("message")
            or "Select a role or paste a job description to tailor your resume.",
        )

    def _run_cover_letter(self, user, workflow, context, params) -> ToolResult:
        return ToolResult(
            tool="cover_letter",
            success=False,
            summary="Cover letter generation requires user confirmation.",
            requires_user=True,
            user_message=params.get("message")
            or "Pick an opportunity to generate a cover letter.",
        )

    def _run_decision(self, user, workflow, _context, _params) -> ToolResult:
        agent = DecisionAgent()
        outcome = agent.generate(user, workflow_id=workflow.id)
        return ToolResult(
            tool="decision",
            success=True,
            summary=outcome["reasoning_summary"],
            data={"decision_execution_id": str(outcome["execution"].id)},
            execution=outcome["execution"],
        )

    def _run_list_applications(self, user, workflow, _context, _params) -> ToolResult:
        applications = self.service.application_repo.list_for_user(user)
        return ToolResult(
            tool="list_applications",
            success=True,
            summary=f"Found {len(applications)} tracked applications.",
            data={"application_count": len(applications)},
        )

    def _run_add_interview(self, user, workflow, _context, params) -> ToolResult:
        return ToolResult(
            tool="add_interview",
            success=False,
            summary="Scheduling interviews requires user confirmation.",
            requires_user=True,
            user_message=params.get("message") or "Confirm interview details to schedule.",
        )

    def _run_ask_user(self, user, workflow, _context, params) -> ToolResult:
        action = params.get("action", "")
        messages = {
            "tailor_resume": "Select a role below or paste a job description to tailor your resume.",
            "cover_letter": "Pick an opportunity to generate a cover letter.",
        }
        return ToolResult(
            tool="ask_user",
            success=True,
            summary="Waiting for user input.",
            requires_user=True,
            user_message=params.get("message") or messages.get(action, "Your input is needed to continue."),
            data={"pending_user_action": action or "input"},
        )
