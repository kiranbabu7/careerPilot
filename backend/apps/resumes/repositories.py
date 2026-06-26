"""Resume persistence."""

from apps.resumes.models import Resume, ResumeAnalysis


class ResumeRepository:
    def list_for_user(self, user) -> list[Resume]:
        return list(Resume.objects.filter(user=user).order_by("-created_at"))

    def get_for_user(self, user, resume_id) -> Resume | None:
        return Resume.objects.filter(user=user, id=resume_id).first()

    def get_active_for_user(self, user) -> Resume | None:
        return Resume.objects.filter(user=user, is_active=True).first()

    def create(
        self,
        *,
        user,
        file,
        original_filename: str,
        content_type: str,
        file_size: int,
        extracted_text: str,
        is_active: bool = False,
    ) -> Resume:
        return Resume.objects.create(
            user=user,
            file=file,
            original_filename=original_filename,
            content_type=content_type,
            file_size=file_size,
            extracted_text=extracted_text,
            is_active=is_active,
        )

    def set_active(self, user, resume: Resume) -> Resume:
        Resume.objects.filter(user=user, is_active=True).update(is_active=False)
        resume.is_active = True
        resume.save(update_fields=["is_active", "updated_at"])
        return resume

    def count_for_user(self, user) -> int:
        return Resume.objects.filter(user=user).count()


class ResumeAnalysisRepository:
    def create(self, *, resume: Resume, **fields) -> ResumeAnalysis:
        return ResumeAnalysis.objects.create(resume=resume, **fields)

    def get_latest_for_resume(self, resume: Resume) -> ResumeAnalysis | None:
        return ResumeAnalysis.objects.filter(resume=resume).first()

    def get_latest_for_resumes(self, resume_ids: list) -> dict:
        analyses = {}
        for resume_id in resume_ids:
            analysis = (
                ResumeAnalysis.objects.filter(resume_id=resume_id)
                .order_by("-created_at")
                .first()
            )
            if analysis:
                analyses[str(resume_id)] = analysis
        return analyses
