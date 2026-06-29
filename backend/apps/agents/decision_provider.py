"""Decision Agent LLM provider with deterministic fallback."""

import logging
from dataclasses import dataclass

from django.conf import settings

from apps.agents.decision_routes import resolve_decision_action_route
from apps.providers.llm.json_output import parse_json_content
from apps.providers.llm.openrouter_chat import invoke_openrouter, openrouter_configured
from apps.resumes.providers import RESUME_ANALYSIS_MODEL

logger = logging.getLogger(__name__)

VALID_ACTION_TYPES = {
    "opportunity",
    "application",
    "interview",
    "material",
    "workflow",
    "agent_run",
    "profile",
}
VALID_URGENCY = {"high", "medium", "low"}


@dataclass
class DecisionGenerationResult:
    summary: str
    rationale: str
    actions: list[dict]
    model_name: str
    used_fallback: bool = False


class DecisionProvider:
    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "").rstrip("/")
        self.model = RESUME_ANALYSIS_MODEL

    def generate(self, prompt_text: str, context: dict) -> DecisionGenerationResult:
        if self._ai_configured():
            try:
                return self._call_ai(prompt_text, context)
            except Exception:
                logger.exception(
                    "AI decision generation failed; using deterministic fallback"
                )
        return self._deterministic_fallback(context)

    def _ai_configured(self) -> bool:
        return openrouter_configured()

    def _call_ai(self, prompt_text: str, context: dict) -> DecisionGenerationResult:
        raw = invoke_openrouter(
            prompt_text,
            model=self.model,
            temperature=0.3,
            timeout=90,
        )
        parsed = parse_json_content(raw)
        return DecisionGenerationResult(
            summary=str(parsed.get("summary", "")),
            rationale=str(parsed.get("rationale", "")),
            actions=self._normalize_actions(parsed.get("actions", []), context),
            model_name=self.model,
            used_fallback=False,
        )

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    def _normalize_actions(self, actions: list, context: dict | None = None) -> list[dict]:
        context = context or {}
        workflow_id = context.get("workflow_id")
        normalized = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("action_type", "profile"))
            if action_type not in VALID_ACTION_TYPES:
                action_type = "profile"
            urgency = str(action.get("urgency", "medium"))
            if urgency not in VALID_URGENCY:
                urgency = "medium"
            payload = {
                "action_type": action_type,
                "target_id": str(action.get("target_id", "")),
                "title": str(action.get("title", "Review next step")),
                "reason": str(action.get("reason", "")),
                "urgency": urgency,
                "route": str(action.get("route", "/")),
            }
            payload["route"] = resolve_decision_action_route(
                payload,
                workflow_id=str(workflow_id) if workflow_id else None,
            )
            normalized.append(payload)
        return normalized[:6]

    def _deterministic_fallback(self, context: dict) -> DecisionGenerationResult:
        actions: list[dict] = []
        counts = context.get("counts", {})

        for opp in context.get("top_opportunities", [])[:3]:
            if opp.get("status") in ("discovered", "saved") and (opp.get("match_score") or 0) >= 70:
                actions.append(
                    {
                        "action_type": "opportunity",
                        "target_id": opp["id"],
                        "title": f"Review {opp['title']} at {opp['company']}",
                        "reason": f"Strong match score ({opp.get('match_score')}).",
                        "urgency": "high",
                        "route": "/opportunities",
                    }
                )

        for app in context.get("applications", []):
            if app.get("stage") == "interviewing":
                actions.append(
                    {
                        "action_type": "application",
                        "target_id": app["id"],
                        "title": f"Prepare for {app['job_title']} interview",
                        "reason": "Application is in interviewing stage.",
                        "urgency": "high",
                        "route": "/applications",
                    }
                )
            elif app.get("stage") == "applied":
                actions.append(
                    {
                        "action_type": "application",
                        "target_id": app["id"],
                        "title": f"Follow up on {app['job_title']}",
                        "reason": "Application submitted — consider interview prep or follow-up.",
                        "urgency": "medium",
                        "route": "/applications",
                    }
                )

        if counts.get("materials", 0) == 0 and counts.get("opportunities", 0) > 0:
            top = context.get("top_opportunities", [{}])[0]
            actions.append(
                {
                    "action_type": "material",
                    "target_id": top.get("id", ""),
                    "title": "Tailor resume for top match",
                    "reason": "No tailored materials yet for high-match roles.",
                    "urgency": "medium",
                    "route": "/opportunities",
                }
            )

        if counts.get("interview_plans", 0) == 0 and counts.get("applications", 0) > 0:
            app = context.get("applications", [{}])[0]
            actions.append(
                {
                    "action_type": "interview",
                    "target_id": app.get("opportunity_id", ""),
                    "title": f"Generate interview prep for {app.get('job_title', 'application')}",
                    "reason": "Tracked applications exist without interview prep.",
                    "urgency": "medium",
                    "route": "/interviews",
                }
            )

        if not actions:
            actions.append(
                {
                    "action_type": "workflow",
                    "target_id": context.get("workflow_id") or "",
                    "title": "Run a career goal workflow",
                    "reason": "Start discovery and evaluation from Home.",
                    "urgency": "high",
                    "route": "/",
                }
            )

        actions.append(
            {
                "action_type": "agent_run",
                "target_id": "",
                "title": "Inspect recent agent runs",
                "reason": "Review what agents have done across your search.",
                "urgency": "low",
                "route": "/agent-runs",
            }
        )

        summary = (
            f"Focus on {actions[0]['title'].lower()} as your top priority."
            if actions
            else "Continue building your job search pipeline."
        )
        rationale = (
            "Deterministic fallback synthesized next actions from opportunities, "
            "applications, materials, and interview prep state."
        )
        return DecisionGenerationResult(
            summary=summary,
            rationale=rationale,
            actions=self._normalize_actions(actions, context),
            model_name="deterministic-fallback",
            used_fallback=True,
        )
