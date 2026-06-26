from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.memory.dashboard import DashboardService
from apps.memory.serializers import DashboardSummarySerializer


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        summary = DashboardService().get_summary(request.user)
        serializer = DashboardSummarySerializer(summary)
        return Response(serializer.data)
