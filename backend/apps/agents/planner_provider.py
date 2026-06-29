"""Planner LLM provider with deterministic fallback."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from django.conf import settings

from apps.providers.llm.json_output import parse_json_content
from apps.providers.llm.openrouter_chat import invoke_openrouter, openrouter_configured

from apps.resumes.providers import RESUME_ANALYSIS_MODEL
from apps.workflows.intent import (
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_CONVERSATIONAL,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    build_planned_agents,
    classify_workflow_intent,
)

logger = logging.getLogger(__name__)

PLANNER_PROMPT_NAME = "planner"

VALID_INTENTS = {
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_CONVERSATIONAL,
}

VALID_TOOLS = {
    "job_search",
    "job_evaluation",
    "company_research",
    "resume_tailor",
    "cover_letter",
    "interview_prep",
    "decision",
    "list_applications",
    "add_interview",
    "ask_user",
}

REPLAN_ACTIONS = {
    "continue",
    "insert_tools",
    "skip_tool",
    "ask_user",
    "complete",
    "fail_with_reason",
}

TOOL_TO_AGENT = {
    "job_search": "job_search",
    "job_evaluation": "job_evaluation",
    "company_research": "company_research",
    "resume_tailor": "resume_tailor",
    "cover_letter": "cover_letter",
    "interview_prep": "interview_prep",
    "decision": "decision",
    "list_applications": "list_applications",
    "add_interview": "add_interview",
    "ask_user": "ask_user",
}

NON_PIPELINE_AGENTS = frozenset({"ask_user", "list_applications", "add_interview"})

AUTO_RUN_TOOLS = {
    "job_search",
    "job_evaluation",
    "company_research",
    "list_applications",
    "decision",
}

CONFIRMATION_TOOLS = {
    "resume_tailor",
    "cover_letter",
    "add_interview",
}


@dataclass
class PlannerGenerationResult:
    intent: str
    constraints: dict
    tool_plan: list[dict]
    success_criteria: list[str]
    reasoning_summary: str
    user_visible_plan: str
    requires_confirmation: bool
    planned_agents: list[str]
    model_name: str
    used_fallback: bool = False


@dataclass
class ReplanResult:
    action: str
    reason: str
    tools_to_insert: list[dict] = field(default_factory=list)
    message: str = ""
    model_name: str = ""
    used_fallback: bool = False


class PlannerProvider:
    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "").rstrip("/")
        self.model = RESUME_ANALYSIS_MODEL

    def generate(self, prompt_text: str, context: dict) -> PlannerGenerationResult:
        if self._ai_configured():
            try:
                return self._call_ai_plan(prompt_text, context)
            except Exception:
                logger.exception("AI planner generation failed; using deterministic fallback")
        return self._deterministic_plan(context)

    def replan(self, prompt_text: str, replan_context: dict) -> ReplanResult:
        if self._ai_configured():
            try:
                return self._call_ai_replan(prompt_text, replan_context)
            except Exception:
                logger.exception("AI replanner failed; using deterministic fallback")
        return self._deterministic_replan(replan_context)

    def _ai_configured(self) -> bool:
        return openrouter_configured()

    def _call_ai_plan(self, prompt_text: str, context: dict) -> PlannerGenerationResult:
        raw = invoke_openrouter(prompt_text, model=self.model, temperature=0.2, timeout=90)
        parsed = parse_json_content(raw)
        return self._normalize_plan(parsed, context, used_fallback=False)

    def _call_ai_replan(self, prompt_text: str, replan_context: dict) -> ReplanResult:
        raw = invoke_openrouter(prompt_text, model=self.model, temperature=0.2, timeout=90)
        parsed = parse_json_content(raw)
        return self._normalize_replan(parsed, used_fallback=False)

    def _normalize_plan(
        self, parsed: dict, context: dict, *, used_fallback: bool
    ) -> PlannerGenerationResult:
        goal = context.get("goal", "")
        default_intent = context.get("workflow_intent") or classify_workflow_intent(goal)
        if default_intent == WORKFLOW_INTENT_CONVERSATIONAL:
            intent = WORKFLOW_INTENT_CONVERSATIONAL
            constraints = {}
            tool_plan: list[dict] = []
        else:
            intent = str(parsed.get("intent", default_intent))
            if intent not in VALID_INTENTS:
                intent = default_intent

            constraints = parsed.get("constraints")
            if not isinstance(constraints, dict):
                constraints = extract_constraints_from_goal(goal)

            tool_plan = self._normalize_tool_plan(parsed.get("tool_plan"), intent, constraints)
        success_criteria = self._normalize_string_list(parsed.get("success_criteria"))
        reasoning_summary = str(
            parsed.get("reasoning_summary") or self._default_reasoning(intent, tool_plan, constraints)
        )
        user_visible_plan = str(
            parsed.get("user_visible_plan") or reasoning_summary
        )
        requires_confirmation = bool(parsed.get("requires_confirmation"))
        if not requires_confirmation:
            requires_confirmation = any(
                step.get("tool") in CONFIRMATION_TOOLS for step in tool_plan
            )

        planned_agents = tool_plan_to_planned_agents(tool_plan, intent)
        model_name = self.model if not used_fallback else "deterministic-fallback"

        return PlannerGenerationResult(
            intent=intent,
            constraints=constraints,
            tool_plan=tool_plan,
            success_criteria=success_criteria,
            reasoning_summary=reasoning_summary,
            user_visible_plan=user_visible_plan,
            requires_confirmation=requires_confirmation,
            planned_agents=planned_agents,
            model_name=model_name,
            used_fallback=used_fallback,
        )

    def _normalize_tool_plan(
        self, raw_plan, intent: str, constraints: dict
    ) -> list[dict]:
        if not isinstance(raw_plan, list) or not raw_plan:
            return build_default_tool_plan(intent, constraints)

        normalized: list[dict] = []
        for step in raw_plan:
            if not isinstance(step, dict):
                continue
            tool = str(step.get("tool", "")).strip()
            if tool not in VALID_TOOLS:
                continue
            auto_run = step.get("auto_run")
            if auto_run is None:
                auto_run = tool in AUTO_RUN_TOOLS
            params = step.get("params")
            if not isinstance(params, dict):
                params = {}
            normalized.append(
                {
                    "tool": tool,
                    "reason": str(step.get("reason", f"Run {tool}.")),
                    "auto_run": bool(auto_run),
                    "params": params,
                }
            )

        if not normalized:
            return build_default_tool_plan(intent, constraints)
        return normalized

    def _normalize_replan(self, parsed: dict, *, used_fallback: bool) -> ReplanResult:
        action = str(parsed.get("action", "continue"))
        if action not in REPLAN_ACTIONS:
            action = "continue"
        tools_raw = parsed.get("tools_to_insert") or []
        tools_to_insert = self._normalize_tool_plan(tools_raw, WORKFLOW_INTENT_JOB_DISCOVERY, {})
        return ReplanResult(
            action=action,
            reason=str(parsed.get("reason", "")),
            tools_to_insert=tools_to_insert,
            message=str(parsed.get("message", "")),
            model_name=self.model if not used_fallback else "deterministic-fallback",
            used_fallback=used_fallback,
        )

    def _normalize_string_list(self, value) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    def _deterministic_plan(self, context: dict) -> PlannerGenerationResult:
        goal = context.get("goal", "")
        intent = context.get("workflow_intent") or classify_workflow_intent(goal)
        constraints = extract_constraints_from_goal(goal)
        tool_plan = build_default_tool_plan(intent, constraints)
        reasoning = self._default_reasoning(intent, tool_plan, constraints)
        success_criteria = default_success_criteria(intent, constraints)
        requires_confirmation = intent in (
            WORKFLOW_INTENT_TAILOR_RESUME,
            WORKFLOW_INTENT_COVER_LETTER,
        )

        return PlannerGenerationResult(
            intent=intent,
            constraints=constraints,
            tool_plan=tool_plan,
            success_criteria=success_criteria,
            reasoning_summary=reasoning,
            user_visible_plan=reasoning,
            requires_confirmation=requires_confirmation,
            planned_agents=tool_plan_to_planned_agents(tool_plan, intent),
            model_name="deterministic-fallback",
            used_fallback=True,
        )

    def _deterministic_replan(self, replan_context: dict) -> ReplanResult:
        last_tool = replan_context.get("last_tool_key", "")
        workflow_result = replan_context.get("workflow_result") or {}
        constraints = workflow_result.get("constraints") or replan_context.get("constraints") or {}
        completed = workflow_result.get("completed_agents") or []
        discovered = workflow_result.get("discovered_count", 0)
        pending_tools = replan_context.get("pending_tools") or []

        if last_tool == "job_search" and discovered == 0:
            pending_tool_keys = [t.get("tool") for t in pending_tools]
            if "job_evaluation" in pending_tool_keys:
                return ReplanResult(
                    action="continue",
                    reason="Run evaluation for linked opportunities even when discovery count is zero.",
                    model_name="deterministic-fallback",
                    used_fallback=True,
                )
            if not workflow_result.get("search_broadened"):
                return ReplanResult(
                    action="insert_tools",
                    reason="Search returned zero listings; broadening query before giving up.",
                    tools_to_insert=[
                        {
                            "tool": "job_search",
                            "reason": "Broaden search after empty results.",
                            "auto_run": True,
                            "params": {"broaden": True},
                        }
                    ],
                    model_name="deterministic-fallback",
                    used_fallback=True,
                )
            return ReplanResult(
                action="ask_user",
                reason="No roles found even after broadening.",
                message=(
                    "No matching roles were found. Consider relaxing location, seniority, "
                    "or company-stage constraints."
                ),
                model_name="deterministic-fallback",
                used_fallback=True,
            )

        pending_tool_keys = [t.get("tool") for t in pending_tools]
        if (
            last_tool == "job_evaluation"
            and constraints.get("requires_company_research")
            and "company_research" not in completed
            and "company_research" not in pending_tool_keys
        ):
            tools_to_insert = [
                {
                    "tool": "company_research",
                    "reason": (
                        "Research companies only for roles that passed initial fit screening."
                    ),
                    "auto_run": True,
                    "params": {},
                },
                {
                    "tool": "job_evaluation",
                    "reason": "Re-score researched roles with company-stage evidence.",
                    "auto_run": True,
                    "params": {},
                },
            ]
            return ReplanResult(
                action="insert_tools",
                reason="Company-stage verification required after initial fit screening.",
                tools_to_insert=tools_to_insert,
                model_name="deterministic-fallback",
                used_fallback=True,
            )

        if last_tool == "company_research":
            return ReplanResult(
                action="continue",
                reason="Company research complete; proceed to final evaluation.",
                model_name="deterministic-fallback",
                used_fallback=True,
            )

        if last_tool == "job_evaluation":
            accepted = workflow_result.get("accepted_count", 0)
            if accepted == 0 and discovered > 0:
                return ReplanResult(
                    action="complete",
                    reason="Evaluation finished with no strong matches; surfacing borderline results.",
                    message=(
                        "Roles were found but none met your match threshold. "
                        "Review borderline matches or adjust constraints."
                    ),
                    model_name="deterministic-fallback",
                    used_fallback=True,
                )

        return ReplanResult(
            action="continue",
            reason="Proceed with remaining planned tools.",
            model_name="deterministic-fallback",
            used_fallback=True,
        )

    def _default_reasoning(
        self, intent: str, tool_plan: list[dict], constraints: dict
    ) -> str:
        tools = " → ".join(step["tool"] for step in tool_plan) or "planner only"
        constraint_bits = []
        for key in ("role", "location", "company_stage", "seniority"):
            if constraints.get(key):
                constraint_bits.append(f"{key}={constraints[key]}")
        constraint_phrase = (
            f" Constraints: {', '.join(constraint_bits)}." if constraint_bits else ""
        )
        return (
            f"Deterministic plan for {intent.replace('_', ' ')}: {tools}."
            f"{constraint_phrase}"
        )


def extract_constraints_from_goal(goal: str) -> dict:
    """Rule-based constraint extraction for fallback and tests."""
    constraints: dict = {}
    normalized = " ".join(goal.lower().split())

    if "remote" in normalized:
        constraints["location"] = "remote"
        constraints["remote_preference"] = "remote"

    seniority_patterns = (
        ("staff", "staff"),
        ("principal", "principal"),
        ("senior", "senior"),
        ("lead", "lead"),
        ("junior", "junior"),
        ("mid-level", "mid-level"),
        ("mid level", "mid-level"),
    )
    for needle, label in seniority_patterns:
        if needle in normalized:
            constraints["seniority"] = label
            break

    role_keywords = (
        "backend engineer",
        "backend developer",
        "backend",
        "frontend",
        "full stack",
        "fullstack",
        "software engineer",
        "platform engineer",
        "devops",
        "sre",
        "data engineer",
        "machine learning",
        "product manager",
    )
    for keyword in role_keywords:
        if keyword in normalized:
            seniority = constraints.get("seniority", "")
            constraints["role"] = f"{seniority} {keyword}".strip() if seniority else keyword
            break

    startup_signals = (
        "growth-stage startup",
        "growth stage startup",
        "growth-stage",
        "early-stage startup",
        "early stage startup",
        "startup",
        "series a",
        "series b",
        "seed stage",
    )
    for signal in startup_signals:
        if signal in normalized:
            constraints["company_stage"] = "growth-stage startup"
            constraints["requires_company_research"] = True
            break

    return constraints


def build_default_tool_plan(intent: str, constraints: dict) -> list[dict]:
    if intent == WORKFLOW_INTENT_JOB_DISCOVERY:
        steps = [
            {
                "tool": "job_search",
                "reason": "Discover roles matching the goal and profile.",
                "auto_run": True,
                "params": {},
            },
            {
                "tool": "job_evaluation",
                "reason": (
                    "Score discovered roles for basic fit (role, skills, location, salary)."
                ),
                "auto_run": True,
                "params": {},
            },
        ]
        if constraints.get("requires_company_research"):
            steps.extend(
                [
                    {
                        "tool": "company_research",
                        "reason": (
                            "Research companies only for roles that passed the match threshold."
                        ),
                        "auto_run": True,
                        "params": {},
                    },
                    {
                        "tool": "job_evaluation",
                        "reason": "Re-score researched roles with company-stage evidence.",
                        "auto_run": True,
                        "params": {},
                    },
                ]
            )
        return steps

    if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        return [
            {
                "tool": "interview_prep",
                "reason": "Generate interview prep from resume and goal.",
                "auto_run": True,
                "params": {},
            }
        ]

    if intent in (WORKFLOW_INTENT_TAILOR_RESUME, WORKFLOW_INTENT_COVER_LETTER):
        return [
            {
                "tool": "ask_user",
                "reason": "User must select a role or paste a job description.",
                "auto_run": False,
                "params": {"action": intent},
            }
        ]

    if intent == WORKFLOW_INTENT_APPLICATION_TRACKING:
        return [
            {
                "tool": "list_applications",
                "reason": "Summarize tracked applications for the user.",
                "auto_run": True,
                "params": {},
            }
        ]

    if intent == WORKFLOW_INTENT_CONVERSATIONAL:
        return []

    return []


def default_success_criteria(intent: str, constraints: dict) -> list[str]:
    if intent == WORKFLOW_INTENT_JOB_DISCOVERY:
        criteria = ["Discover relevant job listings", "Evaluate match scores"]
        if constraints.get("requires_company_research"):
            criteria.insert(1, "Verify company-stage evidence for viable candidates")
        return criteria
    if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        return ["Interview prep plan generated"]
    if intent == WORKFLOW_INTENT_TAILOR_RESUME:
        return ["User selects target role", "Tailored resume generated"]
    if intent == WORKFLOW_INTENT_COVER_LETTER:
        return ["User selects opportunity", "Cover letter generated"]
    if intent == WORKFLOW_INTENT_APPLICATION_TRACKING:
        return ["Application pipeline summarized"]
    if intent == WORKFLOW_INTENT_CONVERSATIONAL:
        return ["Respond conversationally without running agents"]
    return ["Planning complete"]


def tool_plan_to_planned_agents(tool_plan: list[dict], intent: str) -> list[str]:
    agents = ["planner"]
    for step in tool_plan:
        tool = step.get("tool")
        agent = TOOL_TO_AGENT.get(tool)
        if agent and agent not in agents and agent not in NON_PIPELINE_AGENTS:
            agents.append(agent)
    if len(agents) == 1:
        return build_planned_agents(intent)
    return agents
