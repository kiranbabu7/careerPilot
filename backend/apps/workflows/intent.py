"""Rule-based workflow intent classification from user goals."""

import re

WORKFLOW_INTENT_JOB_DISCOVERY = "job_discovery"
WORKFLOW_INTENT_TAILOR_RESUME = "tailor_resume"
WORKFLOW_INTENT_COVER_LETTER = "cover_letter"
WORKFLOW_INTENT_INTERVIEW_PREP = "interview_prep"
WORKFLOW_INTENT_APPLICATION_TRACKING = "application_tracking"
WORKFLOW_INTENT_CONVERSATIONAL = "conversational"

WORKFLOW_INTENTS = (
    WORKFLOW_INTENT_JOB_DISCOVERY,
    WORKFLOW_INTENT_TAILOR_RESUME,
    WORKFLOW_INTENT_COVER_LETTER,
    WORKFLOW_INTENT_INTERVIEW_PREP,
    WORKFLOW_INTENT_APPLICATION_TRACKING,
    WORKFLOW_INTENT_CONVERSATIONAL,
)

_CONVERSATIONAL_HELP_PHRASES: tuple[str, ...] = (
    "what can you do",
    "what do you do",
    "how does this work",
    "commands",
    "capabilities",
    "what are my options",
)

_CONVERSATIONAL_GREETING_PHRASES: tuple[str, ...] = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
)

_OFF_TOPIC_MATH = re.compile(r"what(?:'s| is)\s*\d+\s*[\+\-\*\/]\s*\d+", re.I)

_CAREER_ACTION_PHRASES: tuple[str, ...] = (
    "help me land",
    "help me get",
    "help me find",
    "land a ",
    "get a job",
    "get hired",
    "break into",
    "career in",
    "looking for",
    "want a job",
    "want to work",
)

_CAREER_NOUNS: tuple[str, ...] = (
    "job",
    "jobs",
    "role",
    "roles",
    "position",
    "positions",
    "opening",
    "openings",
)

INTERVIEW_PREP_SCOPE_GENERAL = "general"
INTERVIEW_PREP_SCOPE_APPLICATION = "application_specific"

_GENERAL_PREP_PHRASES: tuple[str, ...] = (
    "everything mentioned in my resume",
    "everything in my resume",
    "mentioned in my resume",
    "revise everything",
    "revise my resume",
    "revision plan",
    "from my resume",
    "based on my resume",
    "my resume content",
    "general interview prep",
    "general prep",
    "practice my resume",
    "review my resume",
)

_APPLICATION_PREP_PHRASES: tuple[str, ...] = (
    "for my interview at",
    "for the interview at",
    "for my interview with",
    "for the interview with",
    "interview at ",
    "interview with ",
    "onsite at ",
    "my onsite at",
    "onsite for ",
    "prepare for my interview",
    "prep for my interview",
    "my application to",
    "application to ",
    "for my role at",
    "for the role at",
    "for my position at",
    "for the position at",
)

_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        WORKFLOW_INTENT_INTERVIEW_PREP,
        (
            "interview prep",
            "interview preparation",
            "prepare for interview",
            "prepare for my interview",
            "mock interview",
            "practice interview",
        ),
    ),
    (
        WORKFLOW_INTENT_COVER_LETTER,
        (
            "cover letter",
            "cover-letter",
            "write a letter",
            "draft a letter",
        ),
    ),
    (
        WORKFLOW_INTENT_TAILOR_RESUME,
        (
            "tailor my resume",
            "tailor resume",
            "tailor the resume",
            "resume tailor",
            "customize my resume",
            "customize resume",
            "update my resume for",
            "rewrite my resume",
        ),
    ),
    (
        WORKFLOW_INTENT_APPLICATION_TRACKING,
        (
            "track application",
            "track my application",
            "application status",
            "application pipeline",
            "manage application",
            "follow up application",
            "follow up on application",
            "where did i apply",
        ),
    ),
    (
        WORKFLOW_INTENT_JOB_DISCOVERY,
        (
            "find job",
            "find jobs",
            "find role",
            "find roles",
            "search job",
            "search for job",
            "search for roles",
            "job search",
            "discover opportunit",
            "look for job",
            "look for role",
            "look for roles",
        ),
    ),
]


def _find_matched_phrase(normalized: str, intent: str) -> str | None:
    """Return the keyword phrase that triggered intent classification, if any."""
    for rule_intent, phrases in _INTENT_KEYWORDS:
        if rule_intent != intent:
            continue
        for phrase in phrases:
            if phrase in normalized:
                return phrase

    if intent == WORKFLOW_INTENT_TAILOR_RESUME:
        if "tailor" in normalized and "resume" in normalized:
            return "tailor + resume"
        if "tailor" in normalized:
            return "tailor"

    if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        if "interview" in normalized:
            return "interview prep/prepare/practice"

    if intent == WORKFLOW_INTENT_APPLICATION_TRACKING:
        if normalized.startswith("apply"):
            return "apply"
        if " help me apply" in f" {normalized}":
            return "help me apply"

    if intent == WORKFLOW_INTENT_CONVERSATIONAL:
        if normalized in ("help", "options"):
            return "help"
        for phrase in _CONVERSATIONAL_HELP_PHRASES:
            if phrase in normalized:
                return phrase
        for greeting in _CONVERSATIONAL_GREETING_PHRASES:
            if normalized == greeting or normalized.startswith(f"{greeting} ") or normalized.startswith(
                f"{greeting},"
            ):
                return greeting
        if _OFF_TOPIC_MATH.search(normalized):
            return "off_topic_math"

    return None


def _normalize_goal(goal: str) -> str:
    return " ".join((goal or "").lower().split())


def _matches_conversational_greeting(normalized: str) -> bool:
    if normalized in _CONVERSATIONAL_GREETING_PHRASES:
        return True
    return any(
        normalized.startswith(f"{greeting} ") or normalized.startswith(f"{greeting},")
        for greeting in _CONVERSATIONAL_GREETING_PHRASES
    )


def _matches_conversational_help(normalized: str) -> bool:
    if normalized in ("help", "options"):
        return True
    return any(phrase in normalized for phrase in _CONVERSATIONAL_HELP_PHRASES)


def _matches_conversational_off_topic(normalized: str, raw: str) -> bool:
    return bool(_OFF_TOPIC_MATH.search(raw) or _OFF_TOPIC_MATH.search(normalized))


def classify_conversational_variant(goal: str) -> str | None:
    """Return greeting|help|off_topic when the goal is meta/help-only."""
    normalized = _normalize_goal(goal)
    if not normalized:
        return None
    if _matches_conversational_greeting(normalized):
        return "greeting"
    if _matches_conversational_off_topic(normalized, goal):
        return "off_topic"
    if _matches_conversational_help(normalized):
        return "help"
    return None


def _has_career_action_signal(normalized: str) -> bool:
    if any(phrase in normalized for phrase in _CAREER_ACTION_PHRASES):
        return True
    return any(noun in normalized for noun in _CAREER_NOUNS)


def classify_workflow_intent(goal: str) -> str:
    """Classify a workflow goal into a pipeline intent (rule-based)."""
    normalized = _normalize_goal(goal)
    if not normalized:
        return WORKFLOW_INTENT_CONVERSATIONAL

    for intent, phrases in _INTENT_KEYWORDS:
        if any(phrase in normalized for phrase in phrases):
            return intent

    if "tailor" in normalized and "resume" in normalized:
        return WORKFLOW_INTENT_TAILOR_RESUME

    if "tailor" in normalized:
        return WORKFLOW_INTENT_TAILOR_RESUME

    if "interview" in normalized and any(
        word in normalized for word in ("prep", "prepare", "practice")
    ):
        return WORKFLOW_INTENT_INTERVIEW_PREP

    if normalized.startswith("apply") or " help me apply" in f" {normalized}":
        return WORKFLOW_INTENT_APPLICATION_TRACKING

    if classify_conversational_variant(goal):
        return WORKFLOW_INTENT_CONVERSATIONAL

    if _has_career_action_signal(normalized):
        return WORKFLOW_INTENT_JOB_DISCOVERY

    return WORKFLOW_INTENT_CONVERSATIONAL


def build_intent_classification(goal: str) -> dict:
    """Structured intent metadata for workflow transparency."""
    normalized = _normalize_goal(goal)
    intent = classify_workflow_intent(goal)
    classification = {
        "intent": intent,
        "method": "rule_based",
        "matched_phrase": _find_matched_phrase(normalized, intent),
        "planned_agents": build_planned_agents(intent),
        "goal_excerpt": (goal or "").strip()[:200],
    }
    if intent == WORKFLOW_INTENT_CONVERSATIONAL:
        classification["conversational_variant"] = (
            classify_conversational_variant(goal) or "help"
        )
    return classification


def is_resume_based_interview_prep(goal: str) -> bool:
    """True when the goal emphasizes revising or practicing resume content."""
    normalized = " ".join((goal or "").lower().split())
    resume_phrases = (
        "mentioned in my resume",
        "everything in my resume",
        "everything mentioned in my resume",
        "revise everything",
        "revise my resume",
        "from my resume",
        "based on my resume",
        "my resume content",
        "practice my resume",
        "review my resume",
    )
    return any(phrase in normalized for phrase in resume_phrases)


def classify_interview_prep_scope(
    goal: str,
    *,
    application_companies: tuple[str, ...] = (),
    opportunity_companies: tuple[str, ...] = (),
) -> str:
    """Classify interview prep as general/resume-based or application-specific."""
    normalized = " ".join((goal or "").lower().split())
    if not normalized:
        return INTERVIEW_PREP_SCOPE_GENERAL

    if any(phrase in normalized for phrase in _GENERAL_PREP_PHRASES):
        return INTERVIEW_PREP_SCOPE_GENERAL

    if any(phrase in normalized for phrase in _APPLICATION_PREP_PHRASES):
        return INTERVIEW_PREP_SCOPE_APPLICATION

    for company in (*application_companies, *opportunity_companies):
        company_norm = " ".join(company.strip().lower().split())
        if len(company_norm) >= 3 and company_norm in normalized:
            return INTERVIEW_PREP_SCOPE_APPLICATION

    return INTERVIEW_PREP_SCOPE_GENERAL


def runs_job_discovery_pipeline(intent: str) -> bool:
    return intent == WORKFLOW_INTENT_JOB_DISCOVERY


def build_planned_agents(intent: str) -> list[str]:
    """Ordered agent keys the workflow will run automatically (on-demand agents excluded)."""
    if intent == WORKFLOW_INTENT_JOB_DISCOVERY:
        return ["planner", "job_search", "job_evaluation"]
    if intent == WORKFLOW_INTENT_INTERVIEW_PREP:
        return ["planner", "interview_prep"]
    return ["planner"]
