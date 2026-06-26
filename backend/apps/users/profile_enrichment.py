"""Conservative profile backfill from resume analysis."""

import re

from apps.users.repositories import UserPreferenceRepository

SKILLS_SPARSE_THRESHOLD = 3

ROLE_PATTERNS = [
    r"(?:senior|staff|principal|lead|junior|mid[\s-]?level)?\s*"
    r"(?:software|backend|frontend|full[\s-]?stack|data|platform|devops|ml|ai)\s+"
    r"(?:engineer|developer|architect)",
    r"(?:product|project|engineering|technical)\s+manager",
    r"(?:data|machine learning|ml)\s+scientist",
    r"(?:site reliability|sre|devops)\s+engineer",
]


class ProfileEnrichmentService:
    def __init__(self, preference_repo: UserPreferenceRepository | None = None):
        self.preference_repo = preference_repo or UserPreferenceRepository()

    def enrich_from_resume(self, user, resume, analysis) -> dict:
        preference, _ = self.preference_repo.get_or_create_for_user(user)
        updates: dict = {}

        if self._is_skills_sparse(preference.skills):
            merged = self._merge_skills(preference.skills, analysis.extracted_skills)
            if merged != preference.skills:
                updates["skills"] = merged

        if not preference.target_roles:
            roles = self._infer_target_roles(resume.extracted_text, analysis)
            if roles:
                updates["target_roles"] = roles

        if not preference.career_goals:
            goals = self._infer_career_goals(resume.extracted_text, analysis, updates.get("target_roles"))
            if goals:
                updates["career_goals"] = goals

        if not updates:
            return {
                "enriched": False,
                "fields_updated": [],
                "preference": preference,
            }

        preference = self.preference_repo.update_preferences(user, **updates)
        return {
            "enriched": True,
            "fields_updated": list(updates.keys()),
            "preference": preference,
            "updates": updates,
        }

    def _is_skills_sparse(self, skills: list) -> bool:
        return len(skills) < SKILLS_SPARSE_THRESHOLD

    def _merge_skills(self, existing: list, extracted: list) -> list:
        seen: set[str] = set()
        merged: list[str] = []
        for skill in list(existing) + list(extracted):
            normalized = str(skill).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
        return merged[:20]

    def _infer_target_roles(self, resume_text: str, analysis) -> list[str]:
        text = resume_text.lower()
        roles: list[str] = []
        seen: set[str] = set()

        for pattern in ROLE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                role = self._title_case_role(match.group(0))
                key = role.lower()
                if key not in seen:
                    seen.add(key)
                    roles.append(role)

        if not roles and analysis.extracted_skills:
            primary_skill = analysis.extracted_skills[0]
            role = f"{primary_skill} Engineer"
            roles.append(role)

        return roles[:3]

    def _infer_career_goals(
        self,
        resume_text: str,
        analysis,
        inferred_roles: list[str] | None,
    ) -> str:
        roles = inferred_roles or self._infer_target_roles(resume_text, analysis)
        role_phrase = roles[0] if roles else "my next role"
        summary_snippet = (analysis.raw_summary or "").strip()
        if summary_snippet:
            first_sentence = summary_snippet.split(".")[0].strip()
            if len(first_sentence) > 20:
                return (
                    f"Advance toward {role_phrase} opportunities. "
                    f"Based on my resume: {first_sentence}."
                )
        return f"Find and land a strong {role_phrase} opportunity that matches my experience."

    @staticmethod
    def _title_case_role(role: str) -> str:
        cleaned = re.sub(r"\s+", " ", role.strip())
        return cleaned.title()
