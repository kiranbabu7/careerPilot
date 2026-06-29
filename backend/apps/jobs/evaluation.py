"""Deterministic job evaluation — scores opportunities against user preferences."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

WEIGHTS = {
    "role_match": 0.25,
    "skill_overlap": 0.25,
    "location_fit": 0.20,
    "salary_fit": 0.15,
    "company_research": 0.15,
}

RECOMMENDATION_THRESHOLDS = (
    (80, "strong_match"),
    (65, "good_match"),
    (45, "moderate_match"),
    (0, "weak_match"),
)

# Minimum match_score shown as a high match in the default list.
HIGH_MATCH_THRESHOLD = 70

# Scores at or above this stay "discovered" (borderline) instead of auto-rejected.
BORDERLINE_MATCH_THRESHOLD = 50


def _normalize_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1}


def _score_role_match(job_title: str, target_roles: list[str]) -> tuple[int, str]:
    if not target_roles:
        return 50, "No target roles configured in profile."

    title_tokens = _normalize_tokens(job_title)
    best_score = 0
    best_role = ""
    for role in target_roles:
        role_tokens = _normalize_tokens(role)
        if not role_tokens:
            continue
        overlap = len(title_tokens & role_tokens)
        score = min(100, int((overlap / len(role_tokens)) * 100))
        if score > best_score:
            best_score = score
            best_role = role

    if best_score >= 70:
        detail = f"Title aligns well with target role: {best_role}."
    elif best_score >= 40:
        detail = f"Partial alignment with target role: {best_role}."
    else:
        detail = "Title does not closely match configured target roles."
    return best_score, detail


def _score_skill_overlap(description: str, skills: list[str]) -> tuple[int, str]:
    if not skills:
        return 50, "No skills configured in profile."

    desc_lower = description.lower()
    matched = [s for s in skills if s.strip() and s.lower() in desc_lower]
    ratio = len(matched) / len(skills)
    score = min(100, int(ratio * 100))

    if matched:
        detail = f"Matched {len(matched)} of {len(skills)} profile skills: {', '.join(matched[:5])}."
    else:
        detail = "No profile skills found in job description."
    return score, detail


def _score_location_fit(
    job_location: str,
    is_remote: bool,
    target_locations: list[str],
    remote_preference: str,
) -> tuple[int, str]:
    pref = (remote_preference or "flexible").lower()

    if is_remote:
        if pref in ("remote", "flexible"):
            return 100, "Remote role matches remote preference."
        return 60, "Remote role but preference favors onsite/hybrid."

    if not target_locations:
        return 70, "No target locations configured; location not penalized."

    job_loc_lower = job_location.lower()
    for loc in target_locations:
        loc_lower = loc.lower()
        if loc_lower in job_loc_lower or job_loc_lower in loc_lower:
            return 100, f"Location matches target: {loc}."
        loc_tokens = _normalize_tokens(loc)
        job_tokens = _normalize_tokens(job_location)
        if loc_tokens & job_tokens:
            return 85, f"Location partially matches target: {loc}."

    if pref == "remote":
        return 30, "Onsite/hybrid role conflicts with remote-only preference."
    return 40, "Location does not match configured target locations."


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _score_salary_fit(
    salary_min,
    salary_max,
    pref_min: int | None,
    pref_max: int | None,
) -> tuple[int, str]:
    job_min = _to_decimal(salary_min)
    job_max = _to_decimal(salary_max)

    if pref_min is None and pref_max is None:
        return 70, "No salary preferences configured."

    if job_min is None and job_max is None:
        return 50, "Job salary not listed."

    effective_job_min = job_min or job_max
    effective_job_max = job_max or job_min

    if pref_min is not None and effective_job_max is not None:
        if effective_job_max < Decimal(pref_min):
            return 25, f"Listed max below minimum preference ({pref_min})."

    if pref_max is not None and effective_job_min is not None:
        if effective_job_min > Decimal(pref_max):
            return 30, f"Listed min above maximum preference ({pref_max})."

    if pref_min is not None and effective_job_min is not None:
        if effective_job_min >= Decimal(pref_min):
            return 95, "Salary meets or exceeds minimum preference."

    return 75, "Salary within acceptable range."


def _coerce_text(value: Any) -> str:
    """Normalize research or constraint values to plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "value", "label", "snippet", "summary"):
            nested = value.get(key)
            if nested:
                return _coerce_text(nested)
        return ""
    return str(value).strip()


def _snippet_corpus(snippets: list) -> str:
    parts: list[str] = []
    for item in snippets:
        if isinstance(item, dict):
            text = _coerce_text(item.get("snippet"))
            title = _coerce_text(item.get("title"))
            combined = f"{title} {text}".strip() if title else text
            if combined:
                parts.append(combined)
        else:
            text = _coerce_text(item)
            if text:
                parts.append(text)
    return " ".join(parts)


def _research_has_content(company_research: dict) -> bool:
    if not company_research:
        return False
    if company_research.get("available"):
        return True
    if _coerce_text(company_research.get("summary")):
        return True
    if company_research.get("snippets"):
        return True
    return any(
        _coerce_text(company_research.get(key))
        for key in ("what_they_do", "recent_news", "funding", "hiring_signals")
    )


def _score_company_stage(company_research: dict, company_stage: str) -> tuple[int, str]:
    """Score whether company research supports a requested company stage."""
    if not company_research or not _research_has_content(company_research):
        return 40, f"Cannot verify {company_stage}; no company research evidence."

    corpus = " ".join(
        [
            _coerce_text(company_research.get("summary")),
            _coerce_text(company_research.get("what_they_do")),
            _coerce_text(company_research.get("recent_news")),
            _coerce_text(company_research.get("funding")),
            _coerce_text(company_research.get("hiring_signals")),
            _snippet_corpus(company_research.get("snippets") or []),
        ]
    ).lower()

    growth_signals = (
        "startup",
        "seed",
        "series a",
        "series b",
        "series c",
        "growth stage",
        "growth-stage",
        "early stage",
        "venture",
        "funding round",
    )
    matched = [signal for signal in growth_signals if signal in corpus]
    if matched:
        return (
            95,
            f"Company research supports {company_stage} signals ({', '.join(matched[:3])}).",
        )
    if "enterprise" in corpus or "fortune" in corpus:
        return 35, f"Research suggests a larger company, not {company_stage}."
    return 55, f"Company research available but {company_stage} signals are inconclusive."


def _score_company_research(
    company_research: dict, *, company_stage: str | None = None
) -> tuple[int, str]:
    """Unavailable research uses a neutral score so it does not auto-reject good role fits."""
    if company_stage:
        return _score_company_stage(company_research, company_stage)

    if not company_research:
        return 50, "No company research available yet (neutral score)."

    if not _research_has_content(company_research):
        reason = company_research.get("reason", "unavailable")
        return 50, f"Company research unavailable ({reason}); neutral score applied."

    summary = (company_research.get("summary") or "").strip()
    snippets = company_research.get("snippets") or []
    section_bits = [
        (company_research.get(key) or "").strip()
        for key in ("what_they_do", "recent_news", "funding", "hiring_signals")
    ]

    if summary:
        preview = summary if len(summary) <= 140 else f"{summary[:137]}..."
        return 100, f"Company research summary available: {preview}"
    if snippets:
        count = len(snippets)
        label = "source" if count == 1 else "sources"
        return 80, f"Company research snippets available ({count} {label})."
    if any(section_bits):
        return 80, "Company research sections available (overview, news, or hiring signals)."
    return 60, "Company research marked available but limited content."


def _recommendation_for_score(score: int) -> str:
    for threshold, label in RECOMMENDATION_THRESHOLDS:
        if score >= threshold:
            return label
    return "weak_match"


def evaluate_opportunity(
    *,
    job_title: str,
    job_description: str,
    job_location: str,
    is_remote: bool,
    salary_min,
    salary_max,
    company_research: dict,
    preferences: dict,
    planner_constraints: dict | None = None,
) -> dict[str, Any]:
    """Return match_score and structured evaluation for an opportunity."""
    target_roles = preferences.get("target_roles") or []
    skills = preferences.get("skills") or []
    target_locations = preferences.get("target_locations") or []
    remote_preference = preferences.get("remote_preference") or "flexible"
    pref_salary_min = preferences.get("salary_min")
    pref_salary_max = preferences.get("salary_max")
    constraints = planner_constraints or {}
    company_stage_raw = constraints.get("company_stage")
    company_stage = _coerce_text(company_stage_raw) or None

    role_score, role_detail = _score_role_match(job_title, target_roles)
    skill_score, skill_detail = _score_skill_overlap(job_description, skills)
    location_score, location_detail = _score_location_fit(
        job_location, is_remote, target_locations, remote_preference
    )
    salary_score, salary_detail = _score_salary_fit(
        salary_min, salary_max, pref_salary_min, pref_salary_max
    )
    research_score, research_detail = _score_company_research(
        company_research or {}, company_stage=company_stage
    )

    factors = {
        "role_match": {"score": role_score, "weight": WEIGHTS["role_match"], "detail": role_detail},
        "skill_overlap": {
            "score": skill_score,
            "weight": WEIGHTS["skill_overlap"],
            "detail": skill_detail,
        },
        "location_fit": {
            "score": location_score,
            "weight": WEIGHTS["location_fit"],
            "detail": location_detail,
        },
        "salary_fit": {
            "score": salary_score,
            "weight": WEIGHTS["salary_fit"],
            "detail": salary_detail,
        },
        "company_research": {
            "score": research_score,
            "weight": WEIGHTS["company_research"],
            "detail": research_detail,
        },
    }

    weighted = sum(f["score"] * f["weight"] for f in factors.values())
    match_score = max(0, min(100, int(round(weighted))))

    strengths: list[str] = []
    gaps: list[str] = []
    for name, factor in factors.items():
        if factor["score"] >= 70:
            strengths.append(factor["detail"])
        elif factor["score"] < 50:
            gaps.append(factor["detail"])

    recommendation = _recommendation_for_score(match_score)
    rationale = (
        f"Overall match score {match_score}/100 ({recommendation.replace('_', ' ')}). "
        f"Strongest: {max(factors, key=lambda k: factors[k]['score']).replace('_', ' ')}. "
    )
    if gaps:
        rationale += f"Gaps: {gaps[0]}"
    else:
        rationale += "No major gaps identified."

    return {
        "match_score": match_score,
        "recommendation": recommendation,
        "rationale": rationale,
        "strengths": strengths[:5],
        "gaps": gaps[:5],
        "factors": factors,
    }
