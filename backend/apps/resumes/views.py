from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.http import HttpResponse

from apps.resumes.pdf_export import (
    generate_ats_resume_pdf_with_engine,
    generate_cover_letter_pdf_with_engine,
)
from apps.resumes.resume_content import content_to_preview_text
from apps.resumes.serializers import (
    ApplicationMaterialSerializer,
    ResumeListItemSerializer,
    ResumeSerializer,
    ResumeUploadSerializer,
)
from apps.resumes.services import ResumeService
from apps.resumes.models import ApplicationMaterialType
from apps.resumes.repositories import ApplicationMaterialRepository
from apps.users.repositories import UserPreferenceRepository


class ResumeListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        items = ResumeService().list_resumes(request.user)
        serializer = ResumeListItemSerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ResumeService().upload_resume(
            request.user,
            serializer.validated_data["file"],
        )
        data = ResumeSerializer(result["resume"]).data
        if result["latest_analysis"]:
            from apps.resumes.serializers import ResumeAnalysisSerializer

            data["latest_analysis"] = ResumeAnalysisSerializer(result["latest_analysis"]).data
        data["used_fallback"] = result.get("used_fallback", False)
        data["profile_enriched"] = result.get("profile_enriched", False)
        data["fields_updated"] = result.get("fields_updated", [])
        return Response(data, status=status.HTTP_201_CREATED)


class ResumeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, resume_id):
        result = ResumeService().get_resume(request.user, resume_id)
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ResumeListItemSerializer(result)
        return Response(serializer.data)


class ResumeSetActiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, resume_id):
        result = ResumeService().set_active(request.user, resume_id)
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ResumeListItemSerializer(result)
        return Response(serializer.data)


class ApplicationMaterialListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        materials = ApplicationMaterialRepository().list_for_user(request.user)
        serializer = ApplicationMaterialSerializer(materials, many=True)
        return Response(serializer.data)


class ApplicationMaterialPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, material_id):
        material = ApplicationMaterialRepository().get_for_user(
            request.user, material_id
        )
        if material is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if material.material_type not in (
            ApplicationMaterialType.TAILORED_RESUME,
            ApplicationMaterialType.COVER_LETTER,
        ):
            return Response(
                {"detail": "PDF export is not available for this material type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        preference, _ = UserPreferenceRepository().get_or_create_for_user(request.user)

        try:
            if material.material_type == ApplicationMaterialType.TAILORED_RESUME:
                pdf_bytes, pdf_engine = generate_ats_resume_pdf_with_engine(
                    material.content,
                    user=request.user,
                    resume_text=material.source_resume.extracted_text or "",
                    target_locations=list(preference.target_locations or []),
                )
                filename_prefix = "tailored-resume"
            else:
                job = material.opportunity.job
                pdf_bytes, pdf_engine = generate_cover_letter_pdf_with_engine(
                    material.content,
                    user=request.user,
                    resume_text=material.source_resume.extracted_text or "",
                    target_locations=list(preference.target_locations or []),
                    company=job.company or "",
                    job_location=job.location or "",
                )
                filename_prefix = "cover-letter"
        except Exception as exc:
            return Response(
                {"detail": f"PDF generation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        material.metadata = {
            **(material.metadata or {}),
            "pdf_engine": pdf_engine,
        }
        material.save(update_fields=["metadata", "updated_at"])

        job_title = material.opportunity.job.title.replace(" ", "-").lower()[:40]
        filename = f"{filename_prefix}-{job_title}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
