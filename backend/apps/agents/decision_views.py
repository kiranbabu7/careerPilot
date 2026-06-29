from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.decision import DecisionAgent
from apps.agents.repositories import DecisionRecommendationRepository
from apps.agents.serializers import (
    DecisionGenerateSerializer,
    DecisionRecommendationDetailSerializer,
    DecisionRecommendationSummarySerializer,
)
from apps.agents.views import _parse_int


class DecisionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        offset = _parse_int(request.query_params.get("offset"), 0, minimum=0)
        limit = _parse_int(request.query_params.get("limit"), 20, minimum=1, maximum=100)
        results, count = DecisionRecommendationRepository().list_for_user(
            request.user,
            workflow_id=request.query_params.get("workflow_id") or None,
            offset=offset,
            limit=limit,
        )
        return Response(
            {
                "count": count,
                "limit": limit,
                "offset": offset,
                "results": DecisionRecommendationSummarySerializer(results, many=True).data,
            }
        )

    def post(self, request):
        serializer = DecisionGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workflow_id = serializer.validated_data.get("workflow_id")
        try:
            result = DecisionAgent().generate(
                request.user,
                workflow_id=workflow_id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "recommendation": DecisionRecommendationDetailSerializer(
                    result["recommendation"]
                ).data,
                "agent_execution_id": str(result["execution"].id),
                "reasoning_summary": result["reasoning_summary"],
            },
            status=status.HTTP_201_CREATED,
        )


class DecisionLatestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        recommendation = DecisionRecommendationRepository().get_latest_for_user(
            request.user
        )
        if recommendation is None:
            return Response({"detail": "No recommendations yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DecisionRecommendationDetailSerializer(recommendation).data)


class DecisionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, recommendation_id):
        recommendation = DecisionRecommendationRepository().get_for_user(
            request.user, recommendation_id
        )
        if recommendation is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DecisionRecommendationDetailSerializer(recommendation).data)
