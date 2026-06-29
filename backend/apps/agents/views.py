from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.repositories import AgentExecutionRepository
from apps.agents.serializers import (
    AgentExecutionDetailSerializer,
    AgentExecutionSummarySerializer,
)


def _parse_int(value, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return minimum
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


class AgentExecutionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        offset = _parse_int(request.query_params.get("offset"), 0, minimum=0)
        limit = _parse_int(request.query_params.get("limit"), 20, minimum=1, maximum=100)

        results, count = AgentExecutionRepository().list_for_user_filtered(
            request.user,
            agent_name=request.query_params.get("agent_name") or None,
            status=request.query_params.get("status") or None,
            workflow_id=request.query_params.get("workflow_id") or None,
            started_after=request.query_params.get("started_after") or None,
            started_before=request.query_params.get("started_before") or None,
            search=request.query_params.get("search") or None,
            offset=offset,
            limit=limit,
        )
        include_detail = request.query_params.get("include_detail") == "true"
        result_serializer = (
            AgentExecutionDetailSerializer(results, many=True)
            if include_detail
            else AgentExecutionSummarySerializer(results, many=True)
        )
        return Response(
            {
                "count": count,
                "limit": limit,
                "offset": offset,
                "results": result_serializer.data,
            }
        )


class AgentExecutionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, execution_id):
        execution = AgentExecutionRepository().get_for_user(request.user, execution_id)
        if execution is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AgentExecutionDetailSerializer(execution).data)
