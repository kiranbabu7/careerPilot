from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.repositories import AgentExecutionRepository
from apps.agents.serializers import AgentExecutionSerializer


class AgentExecutionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        executions = AgentExecutionRepository().list_for_user(request.user)
        serializer = AgentExecutionSerializer(executions[:20], many=True)
        return Response(serializer.data)
