from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workflows.serializers import WorkflowStartSerializer
from apps.workflows.services import WorkflowService


class WorkflowListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        executions = WorkflowService().list_executions(request.user)
        from apps.workflows.serializers import WorkflowExecutionSerializer

        serializer = WorkflowExecutionSerializer(executions, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WorkflowStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = WorkflowService().start_workflow(
            request.user,
            goal=serializer.validated_data["goal"],
        )
        return Response(result, status=status.HTTP_201_CREATED)


class WorkflowJobSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        result = WorkflowService().rerun_job_search(request.user, workflow_id)
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)
