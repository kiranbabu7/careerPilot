"""Follow-up intent router for workflow chat refinement."""

from __future__ import annotations

import re
from typing import Any

from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD, HIGH_MATCH_THRESHOLD
from apps.jobs.models import OpportunityStatus
from apps.workflows.intent import (
    WORKFLOW_INTENT_CONVERSATIONAL,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
)


def _workflow_intent(workflow, workflow_context: dict | None = None) -> str:
    result = workflow.result or {}
    context = workflow_context if workflow_context is not None else (workflow.context or {})
    return result.get("workflow_intent") or context.get(
        "workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY
    )


_EXPLICIT_BEST_PICK_PHRASES = (
    "best match",
    "top match",
    "this job",
    "for the best",
    "highest scoring",
    "top-scoring",
)


def wants_explicit_best_pick(params: dict[str, Any]) -> bool:
    """True when the user explicitly asked to tailor the top/best match."""
    return params.get("pick") == "best"


def should_enable_tailor_selection(
    workflow,
    workflow_context: dict,
    params: dict[str, Any],
) -> bool:
    """Show opportunity picker instead of auto-selecting the top match."""
    if wants_explicit_best_pick(params):
        return False
    result = workflow.result or {}
    if result.get("tailored_material_id"):
        return False
    if result.get("search_rerun_in_progress"):
        return False
    return _workflow_intent(workflow, workflow_context) == WORKFLOW_INTENT_JOB_DISCOVERY

FOLLOW_UP_QUESTION = "question"
FOLLOW_UP_CONFIRM = "confirm"
FOLLOW_UP_RERUN_SEARCH = "rerun_job_search"
FOLLOW_UP_ADJUST_THRESHOLD = "adjust_threshold"
FOLLOW_UP_SHOW_BORDERLINE = "show_borderline"
FOLLOW_UP_SHOW_REJECTED = "show_rejected"
FOLLOW_UP_TAILOR_RESUME = "tailor_resume"
FOLLOW_UP_COVER_LETTER = "generate_cover_letter"
FOLLOW_UP_RESEARCH_COMPANY = "research_company"
FOLLOW_UP_UPDATE_STATUS = "update_opportunity_status"
FOLLOW_UP_GENERATE_DECISION = "generate_decision"
FOLLOW_UP_INTERVIEW_PREP = "generate_interview_prep"
FOLLOW_UP_VIEW_INTERVIEW_PREP = "view_interview_prep"
FOLLOW_UP_VIEW_TAILORED_RESUME = "view_tailored_resume"
FOLLOW_UP_DOWNLOAD_TAILORED_RESUME = "download_tailored_resume"
FOLLOW_UP_VIEW_COVER_LETTER = "view_cover_letter"
FOLLOW_UP_DOWNLOAD_COVER_LETTER = "download_cover_letter"
FOLLOW_UP_ADD_INTERVIEW = "add_interview"
FOLLOW_UP_LIST_APPLICATIONS = "list_applications"
FOLLOW_UP_HELP = "help"

_HELP_PHRASES = (
    "what can you do",
    "what do you do",
    "how does this work",
    "commands",
    "capabilities",
    "what are my options",
)

_GREETING_PHRASES = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
)

_OFF_TOPIC_MATH = re.compile(r"what(?:'s| is)\s*\d+\s*[\+\-\*\/]\s*\d+", re.I)

_RESEARCH_COMPANY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^research(?:\s+the)?\s+(.+?)\s+company(?:\s|$)", re.I),
    re.compile(r"^research(?:\s+the)?\s+company(?:\s+(?:named|called))?\s+(.+?)(?:\s|$)", re.I),
    re.compile(r"^company research(?:\s+(?:for|on|about))?\s+(.+?)(?:\s|$)", re.I),
    re.compile(r"^learn about(?:\s+the)?\s+(.+?)(?:\s+company)?(?:\s|$)", re.I),
    re.compile(r"^tell me about(?:\s+the)?\s+(.+?)(?:\s+company)?(?:\s|$)", re.I),
    re.compile(r"^research(?:\s+the)?\s+(.+)$", re.I),
)

_RESEARCH_COMPANY_GENERIC = frozenset(
    {
        "company",
        "the company",
        "this company",
        "that company",
        "a company",
        "top company",
        "best company",
        "the top company",
    }
)

_ACTION_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        FOLLOW_UP_VIEW_INTERVIEW_PREP,
        (
            "view prep plan",
            "show prep plan",
            "open prep plan",
            "view interview prep plan",
            "show interview prep plan",
            "show my interview prep plan",
            "open interview prep",
            "open my interview prep",
            "view my prep plan",
        ),
    ),
    (
        FOLLOW_UP_ADD_INTERVIEW,
        (
            "add interview",
            "track interview",
            "schedule interview",
            "log interview",
            "i have an interview",
            "interview scheduled",
            "interview at ",
            "interview on ",
            "interview with ",
        ),
    ),
    (
        FOLLOW_UP_INTERVIEW_PREP,
        (
            "interview prep",
            "interview preparation",
            "prepare for interview",
            "prepare for interviews",
            "mock interview",
            "practice interview",
            "generate interview prep",
        ),
    ),
    (
        FOLLOW_UP_LIST_APPLICATIONS,
        (
            "list active",
            "list application",
            "list my application",
            "list my applications",
            "list job application",
            "show my application",
            "show my applications",
            "show application",
            "my applications",
            "application pipeline",
            "application status",
            "where did i apply",
        ),
    ),
    (
        FOLLOW_UP_RERUN_SEARCH,
        (
            "more remote",
            "more jobs",
            "rerun search",
            "search again",
            "find more",
            "show me more",
            "run search",
            "new search",
        ),
    ),
    (
        FOLLOW_UP_ADJUST_THRESHOLD,
        (
            "lower threshold",
            "lower the threshold",
            "match threshold",
            "less strict",
            "more lenient",
        ),
    ),
    (
        FOLLOW_UP_SHOW_BORDERLINE,
        (
            "borderline",
            "show borderline",
            "maybe roles",
            "close matches",
        ),
    ),
    (
        FOLLOW_UP_SHOW_REJECTED,
        (
            "rejected roles",
            "show rejected",
            "why reject",
            "why did you reject",
            "why were these rejected",
        ),
    ),
    (
        FOLLOW_UP_TAILOR_RESUME,
        (
            "tailor resume",
            "tailor my resume",
            "customize resume",
            "rewrite resume",
            "list jobs to select",
            "jobs to select for resume tailor",
            "which job to tailor",
            "pick a role to tailor",
            "show jobs to tailor",
            "select a job to tailor",
            "resume tailor",
        ),
    ),
    (
        FOLLOW_UP_COVER_LETTER,
        (
            "cover letter",
            "write a letter",
            "draft cover",
        ),
    ),
    (
        FOLLOW_UP_RESEARCH_COMPANY,
        (
            "research company",
            "company research",
            "learn about the company",
            "research the company",
        ),
    ),
    (
        FOLLOW_UP_UPDATE_STATUS,
        (
            "save this role",
            "reject this role",
            "mark as applied",
            "save opportunity",
            "reject opportunity",
        ),
    ),
    (
        FOLLOW_UP_GENERATE_DECISION,
        (
            "decision",
            "recommendation",
            "what should i do next",
            "next steps",
            "prioritize",
        ),
    ),
]

_QUESTION_HINTS = (
    "why",
    "what",
    "how",
    "explain",
    "tell me",
    "which",
    "who",
    "when",
    "?",
)

_AFFIRMATIVE_PHRASES = (
    "yes",
    "yep",
    "yeah",
    "yup",
    "sure",
    "ok",
    "okay",
    "confirm",
    "confirmed",
    "go ahead",
    "do it",
    "proceed",
    "sounds good",
    "please do",
    "go for it",
    "let's do it",
    "lets do it",
)


def is_affirmative_confirmation(message: str) -> bool:
    """True when the user is confirming a pending action card."""
    normalized = _normalize(message)
    if not normalized:
        return False
    if normalized in _AFFIRMATIVE_PHRASES:
        return True
    if " but " in normalized:
        return False
    return any(
        normalized.startswith(f"{phrase} ") or normalized.startswith(f"{phrase},")
        for phrase in _AFFIRMATIVE_PHRASES
    )


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _matches_greeting(normalized: str) -> bool:
    if normalized in _GREETING_PHRASES:
        return True
    return any(
        normalized.startswith(f"{greeting} ") or normalized.startswith(f"{greeting},")
        for greeting in _GREETING_PHRASES
    )


def _matches_help(normalized: str) -> bool:
    if normalized in ("help", "options"):
        return True
    return any(phrase in normalized for phrase in _HELP_PHRASES)


def _matches_off_topic(normalized: str, raw: str) -> bool:
    return bool(_OFF_TOPIC_MATH.search(raw) or _OFF_TOPIC_MATH.search(normalized))


def classify_follow_up(message: str) -> dict[str, Any]:
    """Classify a follow-up message into an intent and extracted params."""
    normalized = _normalize(message)
    if not normalized:
        return {"intent": FOLLOW_UP_QUESTION, "params": {}}

    if _matches_greeting(normalized):
        return {"intent": FOLLOW_UP_HELP, "params": {"variant": "greeting"}}

    if _matches_off_topic(normalized, message):
        return {"intent": FOLLOW_UP_HELP, "params": {"variant": "off_topic"}}

    if _matches_help(normalized):
        return {"intent": FOLLOW_UP_HELP, "params": {"variant": "help"}}

    for intent, phrases in _ACTION_RULES:
        if any(phrase in normalized for phrase in phrases):
            return {"intent": intent, "params": _extract_params(intent, normalized, message)}

    if _matches_interview_prep(normalized):
        return {
            "intent": FOLLOW_UP_INTERVIEW_PREP,
            "params": _extract_params(FOLLOW_UP_INTERVIEW_PREP, normalized, message),
        }

    if _matches_list_applications(normalized):
        return {
            "intent": FOLLOW_UP_LIST_APPLICATIONS,
            "params": _extract_params(FOLLOW_UP_LIST_APPLICATIONS, normalized, message),
        }

    if _matches_research_company(normalized):
        return {
            "intent": FOLLOW_UP_RESEARCH_COMPANY,
            "params": _extract_params(FOLLOW_UP_RESEARCH_COMPANY, normalized, message),
        }

    if "remote" in normalized and any(
        word in normalized for word in ("more", "only", "find", "search", "show")
    ):
        return {
            "intent": FOLLOW_UP_RERUN_SEARCH,
            "params": {"remote_preference": "remote"},
        }

    if any(hint in normalized for hint in _QUESTION_HINTS):
        return {"intent": FOLLOW_UP_QUESTION, "params": {}}

    return {"intent": FOLLOW_UP_QUESTION, "params": {}}


def _matches_interview_prep(normalized: str) -> bool:
    if "interview" not in normalized:
        return False
    return any(
        word in normalized
        for word in ("prep", "prepare", "preparation", "practice", "mock")
    )


def _clean_company_name(raw: str) -> str:
    name = " ".join((raw or "").strip().split())
    for suffix in (" company", " inc", " ltd", " llc", " corp", " co"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def _extract_company_name(normalized: str) -> str | None:
    for pattern in _RESEARCH_COMPANY_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        name = _clean_company_name(match.group(1))
        if name and name.lower() not in _RESEARCH_COMPANY_GENERIC:
            return name
    return None


def _matches_research_company(normalized: str) -> bool:
    if any(
        phrase in normalized
        for phrase in (
            "research company",
            "company research",
            "learn about the company",
            "research the company",
        )
    ):
        return True
    return _extract_company_name(normalized) is not None


def _matches_list_applications(normalized: str) -> bool:
    if _matches_interview_prep(normalized):
        return False
    if "application" not in normalized:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "list ",
            "show ",
            "what application",
            "how many application",
            "my application",
        )
    )


def _extract_params(intent: str, normalized: str, raw: str) -> dict[str, Any]:
    params: dict[str, Any] = {}

    if intent == FOLLOW_UP_RERUN_SEARCH:
        if "remote" in normalized:
            params["remote_preference"] = "remote"
        location_match = re.search(
            r"(?:in|near|around)\s+([a-z][a-z\s,]{1,40})",
            normalized,
        )
        if location_match:
            params["location"] = location_match.group(1).strip(" ,")
        role_match = re.search(
            r"(?:for|as)\s+([a-z][a-z\s]{2,40}?)(?:\s+roles?|\s+jobs?|$)",
            normalized,
        )
        if role_match:
            params["query"] = role_match.group(1).strip()

    if intent == FOLLOW_UP_ADJUST_THRESHOLD:
        number_match = re.search(r"(\d{2,3})", raw)
        if number_match:
            params["high_match_threshold"] = int(number_match.group(1))
        else:
            params["delta"] = -10

    if intent == FOLLOW_UP_UPDATE_STATUS:
        if "reject" in normalized:
            params["status"] = OpportunityStatus.REJECTED
        elif "save" in normalized:
            params["status"] = OpportunityStatus.SAVED
        elif "applied" in normalized or "apply" in normalized:
            params["status"] = OpportunityStatus.APPLIED

    if intent == FOLLOW_UP_RESEARCH_COMPANY:
        company_name = _extract_company_name(normalized)
        if company_name:
            params["company_name"] = company_name
        elif "best" in normalized or "top" in normalized or "this job" in normalized:
            params["pick"] = "best"
        else:
            params["pick"] = "best"

    if intent == FOLLOW_UP_TAILOR_RESUME:
        if any(phrase in normalized for phrase in _EXPLICIT_BEST_PICK_PHRASES):
            params["pick"] = "best"

    if intent in (
        FOLLOW_UP_COVER_LETTER,
        FOLLOW_UP_UPDATE_STATUS,
    ):
        if "best" in normalized or "top" in normalized or "this job" in normalized:
            params["pick"] = "best"

    if intent == FOLLOW_UP_TAILOR_RESUME and (
        "cover letter" in normalized or "coverletter" in normalized.replace(" ", "")
    ):
        params["include_cover_letter"] = True

    if intent == FOLLOW_UP_INTERVIEW_PREP:
        params["goal"] = raw.strip()
        if any(
            phrase in normalized
            for phrase in (
                "application",
                "active application",
                "from applications",
                "my pipeline",
            )
        ):
            params["scope"] = "application"
        else:
            params["scope"] = "application"

    if intent == FOLLOW_UP_ADD_INTERVIEW:
        company_match = re.search(
            r"(?:at|with)\s+([a-z0-9][\w\s&.'-]{1,60}?)(?:\s+on\s+|\s+for\s+|\s*$)",
            normalized,
            re.I,
        )
        if company_match:
            params["company"] = _clean_company_name(company_match.group(1)).title()

        title_match = re.search(
            r"(?:for|as)\s+(?:a\s+)?([a-z][\w\s]{2,50}?)(?:\s+(?:role|position|at|with|on)\b|$)",
            normalized,
            re.I,
        )
        if title_match:
            params["job_title"] = title_match.group(1).strip().title()

        date_match = re.search(
            r"\bon\s+(\d{4}-\d{2}-\d{2}(?:[tT ]\d{2}:\d{2})?|\d{1,2}/\d{1,2}/\d{2,4}|\w+\s+\d{1,2}(?:,?\s+\d{4})?)",
            raw,
            re.I,
        )
        if date_match:
            params["scheduled_at_raw"] = date_match.group(1).strip()

        round_match = re.search(
            r"(technical|phone|onsite|behavioral|system design|hiring manager)\s*(?:round|interview)?",
            normalized,
            re.I,
        )
        if round_match:
            params["round_label"] = round_match.group(1).strip().title()

    if intent == FOLLOW_UP_LIST_APPLICATIONS:
        if "interview" in normalized:
            params["stage_filter"] = "interviewing"
        elif "active" in normalized:
            params["stage_filter"] = "active"

    return params


def build_action_cards(
    workflow,
    *,
    intent: str,
    params: dict[str, Any],
    workflow_context: dict,
    opportunities_summary: dict | None = None,
) -> list[dict[str, Any]]:
    """Build structured action cards for executable follow-ups."""
    result = workflow.result or {}
    workflow_intent = result.get("workflow_intent") or workflow_context.get(
        "workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY
    )
    opportunities_summary = opportunities_summary or {}
    cards: list[dict[str, Any]] = []

    if intent == FOLLOW_UP_RERUN_SEARCH and workflow_intent == WORKFLOW_INTENT_JOB_DISCOVERY:
        search_params = {k: v for k, v in params.items() if v is not None}
        label = "Rerun job search"
        if search_params.get("remote_preference") == "remote":
            label = "Rerun search (remote focus)"
        cards.append(
            _action_card(
                key=FOLLOW_UP_RERUN_SEARCH,
                label=label,
                description="Run job discovery again with updated filters.",
                params=search_params,
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_ADJUST_THRESHOLD:
        refinement = workflow_context.get("refinement") or {}
        current = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        delta = params.get("delta", -10)
        target = params.get("high_match_threshold", max(BORDERLINE_MATCH_THRESHOLD, current + delta))
        cards.append(
            _action_card(
                key=FOLLOW_UP_ADJUST_THRESHOLD,
                label=f"Lower match threshold to {target}",
                description=(
                    f"Surface roles scoring {target}+ without changing global defaults."
                ),
                params={"high_match_threshold": target},
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_SHOW_BORDERLINE:
        cards.append(
            _action_card(
                key=FOLLOW_UP_SHOW_BORDERLINE,
                label="Show borderline roles",
                description="Include discovered roles between borderline and high-match thresholds.",
                params={"include_borderline": True},
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_SHOW_REJECTED:
        cards.append(
            _action_card(
                key=FOLLOW_UP_SHOW_REJECTED,
                label="Show rejected roles",
                description="Include roles that were auto-rejected during evaluation.",
                params={"include_rejected": True},
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_TAILOR_RESUME:
        pick = params.get("pick", "best")
        use_selection = should_enable_tailor_selection(workflow, workflow_context, params)
        best = opportunities_summary.get("best_opportunity")
        if use_selection:
            if best:
                cards.append(
                    _action_card(
                        key=FOLLOW_UP_TAILOR_RESUME,
                        label=f"Tailor for top match ({best['title']})",
                        description=(
                            "Skip the picker and tailor immediately for the highest-scoring role."
                        ),
                        params={"pick": "best"},
                        requires_confirmation=True,
                    )
                )
        else:
            cards.append(
                _action_card(
                    key=FOLLOW_UP_TAILOR_RESUME,
                    label="Tailor resume for best match",
                    description=(
                        "Run Resume Tailor on the top-scoring opportunity from this workflow."
                    ),
                    params={"pick": pick},
                    requires_confirmation=True,
                )
            )
        if params.get("include_cover_letter") and not use_selection:
            cards.append(
                _action_card(
                    key=FOLLOW_UP_COVER_LETTER,
                    label="Generate cover letter",
                    description="Draft a cover letter for the same opportunity.",
                    params={"pick": pick},
                    requires_confirmation=True,
                )
            )

    elif intent == FOLLOW_UP_COVER_LETTER:
        cards.append(
            _action_card(
                key=FOLLOW_UP_COVER_LETTER,
                label="Generate cover letter",
                description="Draft a cover letter for the best matching opportunity.",
                params={"pick": params.get("pick", "best")},
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_RESEARCH_COMPANY:
        company_name = params.get("company_name")
        if company_name:
            label = f"Research {company_name}"
            description = (
                f"Run company research for {company_name} — overview, news, "
                "funding, and hiring context."
            )
            card_params = {"company_name": company_name}
        else:
            label = "Research top company"
            description = "Run company research for the highest-ranked opportunity."
            card_params = {"pick": params.get("pick", "best")}
        cards.append(
            _action_card(
                key=FOLLOW_UP_RESEARCH_COMPANY,
                label=label,
                description=description,
                params=card_params,
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_UPDATE_STATUS and params.get("status"):
        status = params["status"]
        cards.append(
            _action_card(
                key=FOLLOW_UP_UPDATE_STATUS,
                label=f"Mark best match as {status}",
                description="Update opportunity status after you confirm.",
                params={"pick": params.get("pick", "best"), "status": status},
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_GENERATE_DECISION:
        cards.append(
            _action_card(
                key=FOLLOW_UP_GENERATE_DECISION,
                label="Generate decision recommendation",
                description="Synthesize next steps across opportunities and applications.",
                params={},
                requires_confirmation=True,
            )
        )

    elif intent in (FOLLOW_UP_INTERVIEW_PREP, FOLLOW_UP_VIEW_INTERVIEW_PREP):
        if intent == FOLLOW_UP_VIEW_INTERVIEW_PREP:
            plan_id = result.get("interview_plan_id")
            if plan_id:
                cards.append(build_view_interview_prep_action(str(plan_id)))
                return cards
        scope = params.get("scope", "application")
        goal = params.get("goal") or "Interview prep for active applications"
        label = "Generate interview prep"
        description = "Run Interview Prep for your highest-priority active application."
        if scope == "application":
            label = "Generate interview prep (active applications)"
            description = (
                "Create an application-specific interview prep plan from your pipeline."
            )
        cards.append(
            _action_card(
                key=FOLLOW_UP_INTERVIEW_PREP,
                label=label,
                description=description,
                params={"scope": scope, "goal": goal},
                requires_confirmation=True,
            )
        )

    elif intent == FOLLOW_UP_ADD_INTERVIEW:
        company = params.get("company") or "the company"
        title = params.get("job_title") or "the role"
        if params.get("company") and params.get("job_title"):
            cards.append(
                _action_card(
                    key=FOLLOW_UP_ADD_INTERVIEW,
                    label=f"Add interview: {title} at {company}",
                    description=(
                        "Track this external interview and add it to your application pipeline."
                    ),
                    params={k: v for k, v in params.items() if v is not None},
                    requires_confirmation=True,
                )
            )

    return cards


def build_contextual_actions(
    workflow,
    opportunities_summary: dict,
    applications_summary: dict | None = None,
    *,
    workflow_context: dict | None = None,
) -> list[dict[str, Any]]:
    """Build up to four contextual action cards for the current workflow state."""
    applications_summary = applications_summary or {}
    workflow_context = workflow_context or workflow.context or {}
    result = workflow.result or {}
    workflow_intent = result.get("workflow_intent") or workflow_context.get(
        "workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY
    )
    discovered = int(result.get("discovered_count") or 0)
    active_count = int(applications_summary.get("active_count") or 0)
    best = opportunities_summary.get("best_opportunity")
    high_match = bool(
        best and int(best.get("match_score") or 0) >= HIGH_MATCH_THRESHOLD
    )

    cards: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def add_card(
        key: str,
        label: str,
        description: str,
        params: dict | None = None,
    ) -> None:
        if len(cards) >= 4 or key in seen_keys:
            return
        seen_keys.add(key)
        cards.append(
            _action_card(
                key=key,
                label=label,
                description=description,
                params=params or {},
                requires_confirmation=True,
            )
        )

    if workflow_intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        add_card(
            FOLLOW_UP_LIST_APPLICATIONS,
            "List applications",
            "See your active application pipeline.",
        )
        add_card(
            FOLLOW_UP_INTERVIEW_PREP,
            "Interview prep (another role)",
            "Generate interview prep for a different application or opportunity.",
            params={
                "scope": "application",
                "goal": "Interview prep for active applications",
            },
        )
    elif workflow_intent == WORKFLOW_INTENT_JOB_DISCOVERY:
        if discovered > 0:
            add_card(
                FOLLOW_UP_RERUN_SEARCH,
                "Rerun job search",
                "Run job discovery again with your current preferences.",
            )
            if best and not result.get("search_rerun_in_progress"):
                add_card(
                    FOLLOW_UP_TAILOR_RESUME,
                    "Tailor resume",
                    "Pick a role below to tailor your resume.",
                )
            add_card(
                FOLLOW_UP_SHOW_REJECTED,
                "Show rejected roles",
                "Review roles that were auto-rejected during evaluation.",
                params={"include_rejected": True},
            )
            add_card(
                FOLLOW_UP_INTERVIEW_PREP,
                "Generate interview prep",
                "Create interview prep from your pipeline or saved roles.",
                params={
                    "scope": "application",
                    "goal": "Interview prep for active applications",
                },
            )
        else:
            add_card(
                FOLLOW_UP_RERUN_SEARCH,
                "Rerun job search",
                "Try job discovery again with your current preferences.",
            )
            add_card(
                FOLLOW_UP_LIST_APPLICATIONS,
                "List applications",
                "See roles you have already saved or applied to.",
            )
            add_card(
                FOLLOW_UP_INTERVIEW_PREP,
                "Generate interview prep",
                "Create interview prep from your pipeline or resume.",
                params={
                    "scope": "application",
                    "goal": "Interview prep for active applications",
                },
            )
            add_card(
                FOLLOW_UP_GENERATE_DECISION,
                "Generate decision",
                "Synthesize next steps across opportunities and applications.",
            )
    elif active_count:
        add_card(
            FOLLOW_UP_INTERVIEW_PREP,
            "Generate interview prep",
            "Create interview prep from your active applications.",
            params={
                "scope": "application",
                "goal": "Interview prep for active applications",
            },
        )
        add_card(
            FOLLOW_UP_LIST_APPLICATIONS,
            "List applications",
            "See your active application pipeline.",
        )

    if high_match:
        add_card(
            FOLLOW_UP_TAILOR_RESUME,
            "Tailor resume",
            "Tailor your resume for the top-scoring opportunity.",
            params={"pick": "best"},
        )
        add_card(
            FOLLOW_UP_COVER_LETTER,
            "Generate cover letter",
            "Draft a cover letter for your best match.",
            params={"pick": "best"},
        )
        add_card(
            FOLLOW_UP_RESEARCH_COMPANY,
            "Research company",
            "Run company research for your highest-ranked opportunity.",
            params={"pick": "best"},
        )

    if active_count and workflow_intent != WORKFLOW_INTENT_INTERVIEW_PREP:
        add_card(
            FOLLOW_UP_INTERVIEW_PREP,
            "Generate interview prep",
            "Create interview prep from your active applications.",
            params={
                "scope": "application",
                "goal": "Interview prep for active applications",
            },
        )
        add_card(
            FOLLOW_UP_LIST_APPLICATIONS,
            "List applications",
            "See your active application pipeline.",
        )

    return cards[:4]


def build_help_reply(
    workflow,
    *,
    variant: str = "help",
) -> str:
    """Build a capability reply scoped to this workflow type."""
    result = workflow.result or {}
    workflow_intent = result.get("workflow_intent") or (workflow.context or {}).get(
        "workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY
    )

    if variant == "greeting":
        intro = (
            f"Hi! I'm your career workflow assistant for '{workflow.name}'. "
            "Here's what I can help with in this workspace:"
        )
    elif variant == "off_topic":
        intro = (
            "I'm your career workflow assistant — here are things I can do "
            "in this workspace:"
        )
    else:
        intro = "Here's what I can help with in this workspace:"

    if workflow_intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        capabilities = (
            "list your applications, generate interview prep for another role, "
            "and answer questions about this prep workflow."
        )
    elif workflow_intent == WORKFLOW_INTENT_JOB_DISCOVERY:
        capabilities = (
            "rerun job search, tailor your resume, show rejected or borderline roles, "
            "generate interview prep, and list your applications."
        )
    elif workflow_intent == WORKFLOW_INTENT_TAILOR_RESUME:
        capabilities = (
            "tailor your resume for a top match, generate a cover letter, "
            "research companies (e.g. 'research Namecheap'), and list your applications."
        )
    elif workflow_intent == WORKFLOW_INTENT_CONVERSATIONAL:
        capabilities = (
            "search for jobs, tailor your resume, write cover letters, "
            "prepare for interviews, track applications, and research companies."
        )
    else:
        capabilities = (
            "tailor your resume, research companies (e.g. 'research Namecheap'), "
            "add external interviews, generate interview prep, list applications, "
            "rerun search, and synthesize decision recommendations."
        )

    return f"{intro} I can {capabilities} Use the action cards below to get started."


def build_assistant_reply(
    workflow,
    *,
    intent: str,
    params: dict[str, Any],
    workflow_context: dict,
    opportunities_summary: dict,
    applications_summary: dict | None = None,
) -> str:
    """Build a conversational assistant reply grounded in workflow state."""
    result = workflow.result or {}
    applications_summary = applications_summary or {}

    if intent == FOLLOW_UP_HELP:
        return build_help_reply(
            workflow,
            variant=params.get("variant", "help"),
        )

    if intent == FOLLOW_UP_LIST_APPLICATIONS:
        return _answer_list_applications(applications_summary, params)

    if intent == FOLLOW_UP_QUESTION:
        return _answer_question(
            workflow,
            opportunities_summary,
            applications_summary=applications_summary,
        )

    if intent == FOLLOW_UP_RERUN_SEARCH:
        bits = ["I can rerun job search"]
        if params.get("remote_preference") == "remote":
            bits.append("with a remote focus")
        if params.get("location"):
            bits.append(f"near {params['location']}")
        if params.get("query"):
            bits.append(f"for {params['query']} roles")
        bits.append("Confirm the action card when you're ready.")
        return " ".join(bits) + "."

    if intent == FOLLOW_UP_ADJUST_THRESHOLD:
        return (
            "I can lower the match threshold for this workspace so borderline roles "
            "surface in refinement views. Confirm to apply the override here only."
        )

    if intent == FOLLOW_UP_SHOW_BORDERLINE:
        borderline = int(result.get("borderline_count") or 0)
        return (
            f"This workflow has {borderline} borderline role(s). "
            "I can include them in refinement results after you confirm."
        )

    if intent == FOLLOW_UP_SHOW_REJECTED:
        rejected = int(result.get("rejected_count") or 0)
        return (
            f"{rejected} role(s) were rejected during evaluation. "
            "Confirm to surface them here for review."
        )

    if intent == FOLLOW_UP_TAILOR_RESUME:
        if should_enable_tailor_selection(workflow, workflow_context, params):
            return "Pick a role below to tailor your resume."
        best = opportunities_summary.get("best_opportunity")
        if best:
            materials = "resume and cover letter" if params.get("include_cover_letter") else "resume"
            return (
                f"Top match: {best['title']} at {best['company']} "
                f"(score {best['match_score']}). Confirm to tailor your {materials}."
            )
        return "No evaluated opportunities yet. Run job search or evaluate roles first."

    if intent == FOLLOW_UP_COVER_LETTER:
        return "I can generate a cover letter for your best match. Confirm to proceed."

    if intent == FOLLOW_UP_RESEARCH_COMPANY:
        company_name = params.get("company_name")
        if company_name:
            return (
                f"I can research {company_name} — business overview, news, funding, "
                "and hiring context. Confirm the action card when you're ready."
            )
        return (
            "I can research the company behind your top opportunity. "
            "Confirm to run research."
        )

    if intent == FOLLOW_UP_UPDATE_STATUS:
        status = params.get("status", "saved")
        return f"I can update the best match to '{status}'. Confirm before I apply the change."

    if intent == FOLLOW_UP_GENERATE_DECISION:
        return (
            "I can synthesize a decision recommendation from your pipeline. "
            "Confirm to run the Decision agent."
        )

    if intent == FOLLOW_UP_ADD_INTERVIEW:
        company = params.get("company")
        title = params.get("job_title")
        if company and title:
            when = ""
            if params.get("scheduled_at_raw"):
                when = f" on {params['scheduled_at_raw']}"
            return (
                f"I can add an interview for {title} at {company}{when}. "
                "Confirm the action card when you're ready."
            )
        return (
            "I can track an external interview for you. Share the company and job title "
            "(e.g. 'Add interview for Staff Engineer at Acme on 2026-03-15')."
        )

    if intent == FOLLOW_UP_VIEW_INTERVIEW_PREP:
        plan_id = result.get("interview_plan_id")
        if plan_id:
            return (
                "Your interview prep plan is ready. "
                "Use View prep plan below to open your roadmap and practice questions."
            )
        return (
            "No prep plan yet for this workflow. "
            "Confirm Generate interview prep below to create one."
        )

    if intent == FOLLOW_UP_INTERVIEW_PREP:
        target = applications_summary.get("top_prep_target")
        if target:
            return (
                f"I can generate application-specific interview prep for "
                f"{target['title']} at {target['company']} ({target['stage']}). "
                "Confirm the action card when you're ready."
            )
        active_count = int(applications_summary.get("active_count") or 0)
        if active_count:
            return (
                f"You have {active_count} active application(s). I can generate "
                "interview prep from your pipeline — confirm the action card when ready."
            )
        return (
            "I can generate interview prep from your saved opportunities or resume. "
            "Confirm the action card when you're ready."
        )

    return _answer_question(
        workflow,
        opportunities_summary,
        applications_summary=applications_summary,
    )


def _answer_list_applications(applications_summary: dict, params: dict) -> str:
    applications = applications_summary.get("applications") or []
    stage_filter = params.get("stage_filter")
    if stage_filter == "interviewing":
        applications = [
            app for app in applications if app.get("stage") == "interviewing"
        ]
    elif stage_filter == "active":
        applications = [
            app
            for app in applications
            if app.get("stage") not in ("rejected", "withdrawn")
        ]

    if not applications:
        total = int(applications_summary.get("total_count") or 0)
        if total:
            return (
                f"You have {total} application(s) on file, but none match that filter. "
                "Try listing all applications or ask for interview prep."
            )
        return (
            "You have no tracked applications yet. Save or apply to roles from "
            "Opportunities, then ask again."
        )

    lines = [f"You have {len(applications)} application(s):"]
    for app in applications[:8]:
        score = app.get("match_score")
        score_text = f", match {score}/100" if score is not None else ""
        lines.append(
            f"- {app['title']} at {app['company']} ({app['stage']}{score_text})"
        )
    if len(applications) > 8:
        lines.append(f"...and {len(applications) - 8} more.")
    lines.append(
        "Ask to generate interview prep for active applications when you want a prep plan."
    )
    return " ".join(lines)


def _answer_question(
    workflow,
    opportunities_summary: dict,
    *,
    applications_summary: dict | None = None,
) -> str:
    result = workflow.result or {}
    rejected = int(result.get("rejected_count") or 0)
    borderline = int(result.get("borderline_count") or 0)
    accepted = int(result.get("accepted_count") or 0)
    evaluated = int(result.get("evaluated_count") or 0)
    discovered = int(result.get("discovered_count") or 0)
    top_score = int(result.get("top_match_score") or 0)

    lines = [
        f"Workflow '{workflow.name}' is {workflow.status}.",
    ]
    if discovered:
        lines.append(f"Job search discovered {discovered} role(s).")
    if evaluated:
        lines.append(
            f"Evaluation: {accepted} high match, {borderline} borderline, "
            f"{rejected} rejected (top score {top_score})."
        )
    if rejected and opportunities_summary.get("sample_rejected"):
        sample = opportunities_summary["sample_rejected"][0]
        gaps = (sample.get("evaluation") or {}).get("gaps") or []
        gap_text = gaps[0] if gaps else sample.get("match_context") or "low overall match score"
        lines.append(f"Example rejection driver: {gap_text}")

    best = opportunities_summary.get("best_opportunity")
    if best:
        lines.append(
            f"Best current match: {best['title']} at {best['company']} ({best['match_score']}/100)."
        )

    applications_summary = applications_summary or {}
    active_count = int(applications_summary.get("active_count") or 0)
    if active_count:
        lines.append(f"You have {active_count} active application(s) in your pipeline.")

    lines.append(_contextual_suggestions(workflow, opportunities_summary, applications_summary))
    return " ".join(lines)


def _contextual_suggestions(
    workflow,
    opportunities_summary: dict,
    applications_summary: dict,
) -> str:
    result = workflow.result or {}
    workflow_intent = result.get("workflow_intent") or (workflow.context or {}).get(
        "workflow_intent", WORKFLOW_INTENT_JOB_DISCOVERY
    )
    discovered = int(result.get("discovered_count") or 0)
    active_count = int(applications_summary.get("active_count") or 0)
    suggestions: list[str] = []

    if workflow_intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        suggestions.append(
            "Ask to list active applications or generate interview prep for another role."
        )
    elif workflow_intent == WORKFLOW_INTENT_JOB_DISCOVERY and discovered:
        suggestions.append(
            "Try asking to rerun search, tailor a resume, show rejected roles, "
            "or generate interview prep."
        )
    elif active_count:
        suggestions.append(
            "Ask to list active applications, research a company by name, "
            "or generate interview prep for your pipeline."
        )
    else:
        suggestions.append(
            "Ask to tailor a resume, research a company, rerun search, "
            "or generate interview prep."
        )

    return " ".join(suggestions)


def build_view_interview_prep_action(interview_plan_id: str) -> dict:
    """Link-style action card to open a generated interview prep plan."""
    return {
        "key": FOLLOW_UP_VIEW_INTERVIEW_PREP,
        "label": "View prep plan",
        "description": "Open your generated interview prep roadmap and practice questions.",
        "params": {"interview_plan_id": interview_plan_id},
        "requires_confirmation": False,
        "href": f"/interviews?selected={interview_plan_id}",
        "endpoint_hint": "",
    }


def build_view_tailored_resume_action(material_id: str) -> dict:
    """Link-style action card to preview a tailored resume in mission control."""
    return {
        "key": FOLLOW_UP_VIEW_TAILORED_RESUME,
        "label": "View tailored resume",
        "description": "Preview your tailored resume in mission control.",
        "params": {"material_id": material_id},
        "requires_confirmation": False,
        "endpoint_hint": "",
    }


def build_download_tailored_resume_action(material_id: str) -> dict:
    """Link-style action card to download a tailored resume PDF."""
    return {
        "key": FOLLOW_UP_DOWNLOAD_TAILORED_RESUME,
        "label": "Download PDF",
        "description": "Download your tailored resume as a PDF.",
        "params": {"material_id": material_id},
        "requires_confirmation": False,
        "endpoint_hint": "",
    }


def build_tailored_resume_follow_up_actions(material_id: str) -> list[dict]:
    return [
        build_view_tailored_resume_action(material_id),
        build_download_tailored_resume_action(material_id),
    ]


def build_view_cover_letter_action(material_id: str) -> dict:
    """Link-style action card to preview a generated cover letter in mission control."""
    return {
        "key": FOLLOW_UP_VIEW_COVER_LETTER,
        "label": "View cover letter",
        "description": "Preview your generated cover letter in mission control.",
        "params": {"material_id": material_id},
        "requires_confirmation": False,
        "endpoint_hint": "",
    }


def build_download_cover_letter_action(material_id: str) -> dict:
    """Link-style action card to download a cover letter PDF."""
    return {
        "key": FOLLOW_UP_DOWNLOAD_COVER_LETTER,
        "label": "Download PDF",
        "description": "Download your cover letter as a PDF.",
        "params": {"material_id": material_id},
        "requires_confirmation": False,
        "endpoint_hint": "",
    }


def build_cover_letter_follow_up_actions(material_id: str) -> list[dict]:
    return [
        build_view_cover_letter_action(material_id),
        build_download_cover_letter_action(material_id),
    ]


def _action_card(
    *,
    key: str,
    label: str,
    description: str,
    params: dict,
    requires_confirmation: bool,
) -> dict:
    return {
        "key": key,
        "label": label,
        "description": description,
        "params": params,
        "requires_confirmation": requires_confirmation,
        "endpoint_hint": f"actions/{key}",
    }
