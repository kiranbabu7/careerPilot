"""Resume business logic."""

import logging

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.memory.services import ActivityService, MemoryService
from apps.resumes.extraction import ExtractionError, extract_text, validate_resume_file
from apps.resumes.providers import ResumeAnalysisProvider
from apps.resumes.repositories import ResumeAnalysisRepository, ResumeRepository
from apps.users.profile_enrichment import ProfileEnrichmentService
from apps.users.repositories import UserPreferenceRepository

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(
        self,
        resume_repo: ResumeRepository | None = None,
        analysis_repo: ResumeAnalysisRepository | None = None,
        preference_repo: UserPreferenceRepository | None = None,
        analysis_provider: ResumeAnalysisProvider | None = None,
        memory_service: MemoryService | None = None,
        activity_service: ActivityService | None = None,
        enrichment_service: ProfileEnrichmentService | None = None,
    ):
        self.resume_repo = resume_repo or ResumeRepository()
        self.analysis_repo = analysis_repo or ResumeAnalysisRepository()
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.analysis_provider = analysis_provider or ResumeAnalysisProvider()
        self.memory_service = memory_service or MemoryService()
        self.activity_service = activity_service or ActivityService()
        self.enrichment_service = enrichment_service or ProfileEnrichmentService()

    def list_resumes(self, user):
        resumes = self.resume_repo.list_for_user(user)
        resume_ids = [r.id for r in resumes]
        latest_analyses = self.analysis_repo.get_latest_for_resumes(resume_ids)
        return [
            {
                "resume": resume,
                "latest_analysis": latest_analyses.get(str(resume.id)),
            }
            for resume in resumes
        ]

    def get_resume(self, user, resume_id):
        resume = self.resume_repo.get_for_user(user, resume_id)
        if resume is None:
            return None
        return {
            "resume": resume,
            "latest_analysis": self.analysis_repo.get_latest_for_resume(resume),
        }

    @transaction.atomic
    def upload_resume(self, user, uploaded_file) -> dict:
        filename = uploaded_file.name
        content_type = getattr(uploaded_file, "content_type", "") or ""
        file_size = uploaded_file.size

        max_size = getattr(settings, "RESUME_MAX_UPLOAD_SIZE", 5 * 1024 * 1024)
        try:
            validate_resume_file(filename, content_type, file_size, max_size)
            uploaded_file.seek(0)
            extracted_text = extract_text(uploaded_file, filename)
        except ExtractionError as exc:
            raise ValidationError({"file": str(exc)}) from exc

        is_first = self.resume_repo.count_for_user(user) == 0
        uploaded_file.seek(0)
        resume = self.resume_repo.create(
            user=user,
            file=uploaded_file,
            original_filename=filename,
            content_type=content_type,
            file_size=file_size,
            extracted_text=extracted_text,
            is_active=is_first,
        )

        self.activity_service.record_resume_uploaded(user, resume)
        self.memory_service.record_resume_context(user, resume)

        preferences = self._preference_dict(user)
        analysis_result = self.analysis_provider.analyze(extracted_text, preferences)
        analysis = self.analysis_repo.create(
            resume=resume,
            model_name=analysis_result.model_name,
            raw_summary=analysis_result.raw_summary,
            health_score=analysis_result.health_score,
            ats_score=analysis_result.ats_score,
            strengths=analysis_result.strengths,
            weaknesses=analysis_result.weaknesses,
            missing_keywords=analysis_result.missing_keywords,
            improvement_suggestions=analysis_result.improvement_suggestions,
            extracted_skills=analysis_result.extracted_skills,
        )

        self.activity_service.record_resume_analyzed(user, resume, analysis)
        self.memory_service.record_analysis_context(user, resume, analysis)

        enrichment = self.enrichment_service.enrich_from_resume(user, resume, analysis)
        if enrichment["enriched"]:
            self.activity_service.record_profile_enriched(user, enrichment["fields_updated"])
            self.memory_service.record_profile_enriched(
                user,
                enrichment["fields_updated"],
                enrichment.get("updates", {}),
            )

        return {
            "resume": resume,
            "latest_analysis": analysis,
            "used_fallback": analysis_result.used_fallback,
            "profile_enriched": enrichment["enriched"],
            "fields_updated": enrichment["fields_updated"],
        }

    def set_active(self, user, resume_id) -> dict | None:
        resume = self.resume_repo.get_for_user(user, resume_id)
        if resume is None:
            return None
        resume = self.resume_repo.set_active(user, resume)
        return {
            "resume": resume,
            "latest_analysis": self.analysis_repo.get_latest_for_resume(resume),
        }

    def _preference_dict(self, user) -> dict:
        preference, _ = self.preference_repo.get_or_create_for_user(user)
        return {
            "target_roles": preference.target_roles,
            "target_locations": preference.target_locations,
            "remote_preference": preference.remote_preference,
            "career_goals": preference.career_goals,
            "skills": preference.skills,
        }
