from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.resumes.serializers import (
    ResumeListItemSerializer,
    ResumeSerializer,
    ResumeUploadSerializer,
)
from apps.resumes.services import ResumeService


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
