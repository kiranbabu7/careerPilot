"""Dashboard summary business logic."""

from apps.memory.repositories import ActivityRepository
from apps.memory.serializers import ActivityEventSerializer
from apps.resumes.repositories import ResumeAnalysisRepository, ResumeRepository
from apps.users.repositories import UserPreferenceRepository
from apps.users.serializers import UserPreferenceSerializer

PROFILE_SIGNALS = [
    ("target_roles", "Target roles", 20),
    ("locations", "Locations or remote preference", 15),
    ("career_goals", "Career goals", 15),
    ("skills", "Skills", 10),
    ("salary", "Salary range", 10),
    ("resume", "Active resume", 20),
    ("resume_analysis", "Resume analysis", 10),
]


class DashboardService:
    def __init__(
        self,
        preference_repo: UserPreferenceRepository | None = None,
        resume_repo: ResumeRepository | None = None,
        analysis_repo: ResumeAnalysisRepository | None = None,
        activity_repo: ActivityRepository | None = None,
    ):
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.resume_repo = resume_repo or ResumeRepository()
        self.analysis_repo = analysis_repo or ResumeAnalysisRepository()
        self.activity_repo = activity_repo or ActivityRepository()

    def get_summary(self, user) -> dict:
        preference, _ = self.preference_repo.get_or_create_for_user(user)
        active_resume = self.resume_repo.get_active_for_user(user)
        active_analysis = (
            self.analysis_repo.get_latest_for_resume(active_resume)
            if active_resume
            else None
        )
        recent_activity = self.activity_repo.list_recent(user, limit=10)

        signals = self._completion_signals(preference, active_resume, active_analysis)
        profile_completion = self._calculate_profile_completion(signals)
        preferences_summary = self._preferences_summary(preference)
        next_actions = self._next_actions(preference, active_resume, active_analysis, signals)

        return {
            "profile_completion": profile_completion,
            "completion_signals": signals,
            "active_resume": self._resume_summary(active_resume, active_analysis),
            "preferences_summary": preferences_summary,
            "recent_activity": ActivityEventSerializer(recent_activity, many=True).data,
            "next_actions": next_actions,
        }

    def _completion_signals(self, preference, active_resume, active_analysis) -> dict:
        completed: list[dict] = []
        missing: list[dict] = []

        checks = {
            "target_roles": bool(preference.target_roles),
            "locations": bool(
                preference.target_locations or preference.remote_preference != "flexible"
            ),
            "career_goals": bool(preference.career_goals),
            "skills": bool(preference.skills),
            "salary": bool(preference.salary_min or preference.salary_max),
            "resume": active_resume is not None,
            "resume_analysis": active_analysis is not None,
        }

        labels = {key: label for key, label, _ in PROFILE_SIGNALS}
        weights = {key: weight for key, _, weight in PROFILE_SIGNALS}

        for key, done in checks.items():
            entry = {"key": key, "label": labels[key], "weight": weights[key]}
            if done:
                completed.append(entry)
            else:
                missing.append(entry)

        return {"completed": completed, "missing": missing}

    def _calculate_profile_completion(self, signals: dict) -> int:
        score = sum(item["weight"] for item in signals["completed"])
        return min(100, score)

    def _preferences_summary(self, preference) -> dict:
        data = UserPreferenceSerializer(preference).data
        return {
            "target_roles": data["target_roles"],
            "target_locations": data["target_locations"],
            "remote_preference": data["remote_preference"],
            "skills_count": len(data["skills"]),
            "has_career_goals": bool(data["career_goals"]),
        }

    def _resume_summary(self, resume, analysis) -> dict | None:
        if resume is None:
            return None
        summary = {
            "id": str(resume.id),
            "original_filename": resume.original_filename,
            "is_active": resume.is_active,
            "uploaded_at": resume.created_at.isoformat(),
        }
        if analysis:
            summary["health_score"] = analysis.health_score
            summary["ats_score"] = analysis.ats_score
            summary["model_name"] = analysis.model_name
        return summary

    def _next_actions(
        self,
        preference,
        active_resume,
        active_analysis,
        signals: dict,
    ) -> list[dict]:
        missing_keys = {item["key"] for item in signals["missing"]}
        actions: list[dict] = []

        if "target_roles" in missing_keys:
            actions.append({
                "key": "set_target_roles",
                "title": "Add target roles",
                "description": "Tell CareerPilot which roles you're pursuing.",
                "href": "/settings",
            })
        if "career_goals" in missing_keys:
            actions.append({
                "key": "set_career_goals",
                "title": "Define your career goals",
                "description": "Share what success looks like for your next move.",
                "href": "/settings",
            })
        if "resume" in missing_keys:
            actions.append({
                "key": "upload_resume",
                "title": "Upload your resume",
                "description": "Upload your resume and CareerPilot will finish your profile from it.",
                "href": "/resume",
            })
        elif active_analysis and active_analysis.health_score < 70:
            actions.append({
                "key": "improve_resume",
                "title": "Improve your resume",
                "description": "Review suggestions to boost your resume health score.",
                "href": "/resume",
            })
        if "skills" in missing_keys and active_resume is not None:
            actions.append({
                "key": "add_skills",
                "title": "Add skills",
                "description": "Upload a resume or add skills in settings.",
                "href": "/settings",
            })
        if not actions:
            actions.append({
                "key": "start_workspace",
                "title": "Start a career goal",
                "description": "Describe what you want to accomplish on Home.",
                "href": "/",
            })
        return actions[:4]
