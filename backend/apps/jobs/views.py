from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.serializers import OpportunityListSerializer, OpportunitySerializer
from apps.jobs.repositories import OpportunityRepository


class OpportunityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        opportunities = OpportunityRepository().list_for_user(request.user)
        serializer = OpportunityListSerializer(opportunities, many=True)
        return Response(serializer.data)


class OpportunityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)
        serializer = OpportunitySerializer(opportunity)
        return Response(serializer.data)
