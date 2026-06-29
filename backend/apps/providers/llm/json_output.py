"""Shared JSON parsing for LLM text responses."""

from __future__ import annotations

import json
import re


def parse_json_content(raw: str) -> dict:
    """Parse JSON from LLM output, stripping optional markdown fences."""
    cleaned = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    elif cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object from LLM response")
    return parsed
