"""Build selectable tailor targets for resume tailoring workflows."""

from __future__ import annotations

import re

from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD, HIGH_MATCH_THRESHOLD
from apps.jobs.models import Opportunity, OpportunityStatus

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "my",
        "of",
        "or",
        "positions",
        "position",
        "resume",
        "roles",
        "role",
        "the",
        "to",
        "tailor",
        "customize",
        "update",
        "rewrite",
    }
)


def _extract_goal_keywords(goal: str) -> set[str]:
    normalized = " ".join((goal or "").lower().split())
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 2 and token not in _STOP_WORDS
    }
    return tokens


def _is_eligible_for_tailor(opportunity: Opportunity) -> bool:
    score = opportunity.match_score
    if score is None:
        return False

    status = opportunity.status
    if status in (OpportunityStatus.SAVED, OpportunityStatus.APPLIED):
        return True
    if score >= HIGH_MATCH_THRESHOLD:
        return True
    if status == OpportunityStatus.DISCOVERED and score >= BORDERLINE_MATCH_THRESHOLD:
        return True
    return False


def _score_opportunity_relevance(opportunity: Opportunity, keywords: set[str]) -> int:
    if not keywords:
        return opportunity.match_score or 0

    job = opportunity.job
    haystack = " ".join(
        [
            job.title or "",
            job.company or "",
            job.description or "",
        ]
    ).lower()
    haystack_tokens = set(re.findall(r"[a-z0-9]+", haystack))

    overlap = len(keywords & haystack_tokens)
    keyword_score = min(100, overlap * 20)
    match_score = opportunity.match_score or 0

    status_boost = 0
    if opportunity.status == OpportunityStatus.SAVED:
        status_boost = 15
    elif opportunity.status == OpportunityStatus.APPLIED:
        status_boost = 10
    elif match_score >= HIGH_MATCH_THRESHOLD:
        status_boost = 8

    return keyword_score + match_score + status_boost


def serialize_tailor_opportunity(opportunity: Opportunity) -> dict:
    job = opportunity.job
    return {
        "id": str(opportunity.id),
        "title": job.title,
        "company": job.company,
        "match_score": opportunity.match_score,
        "status": opportunity.status,
        "location": job.location or "",
        "is_remote": job.is_remote,
    }


def build_tailor_options(
    opportunities: list[Opportunity],
    goal: str,
    *,
    limit: int = 10,
    include_recent: bool = True,
) -> dict:
    """Return ranked opportunities plus custom JD support flag."""
    keywords = _extract_goal_keywords(goal)

    eligible = [opp for opp in opportunities if _is_eligible_for_tailor(opp)]
    ranked = sorted(
        eligible,
        key=lambda opp: _score_opportunity_relevance(opp, keywords),
        reverse=True,
    )

    selected_ids = {str(opp.id) for opp in ranked[:limit]}

    if include_recent and len(ranked) < limit:
        recent = sorted(
            opportunities,
            key=lambda opp: opp.created_at,
            reverse=True,
        )
        for opp in recent:
            if opp.match_score is None:
                continue
            opp_id = str(opp.id)
            if opp_id in selected_ids:
                continue
            ranked.append(opp)
            selected_ids.add(opp_id)
            if len(ranked) >= limit:
                break

    return {
        "opportunities": [serialize_tailor_opportunity(opp) for opp in ranked[:limit]],
        "supports_custom_jd": True,
        "keyword_hints": sorted(keywords)[:8],
    }
