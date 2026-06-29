from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workflows.serializers import (
    WorkflowActionSerializer,
    WorkflowExecutionListSerializer,
    WorkflowExecutionSerializer,
    WorkflowPostMessageSerializer,
    WorkflowStartSerializer,
    WorkflowTailorResumeSerializer,
)
from apps.workflows.chat_service import WorkflowChatService
from apps.workflows.services import WorkflowService
from apps.workflows.timeline import WorkflowTimelineService


class WorkflowListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        executions = WorkflowService().list_executions(request.user)
        serializer = WorkflowExecutionListSerializer(executions, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WorkflowStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = WorkflowService().start_workflow(
            request.user,
            goal=serializer.validated_data["goal"],
        )
        return Response(result, status=status.HTTP_201_CREATED)


class WorkflowDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        workflow = WorkflowService().get_execution(request.user, workflow_id)
        if workflow is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(WorkflowService().build_detail_response(workflow))


class WorkflowJobSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        result = WorkflowService().rerun_job_search(request.user, workflow_id)
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


class WorkflowTailorOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        result = WorkflowService().get_tailor_options(request.user, workflow_id)
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if result.get("detail") and "workflow_id" not in result:
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class WorkflowTailorResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        serializer = WorkflowTailorResumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = WorkflowService().tailor_resume(
            request.user,
            workflow_id,
            opportunity_id=data.get("opportunity_id"),
            job_description=data.get("job_description"),
            title=data.get("title"),
            company=data.get("company"),
        )
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if result.get("error") == "invalid_intent":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        if result.get("error") == "not_found":
            return Response({"detail": result["detail"]}, status=status.HTTP_404_NOT_FOUND)
        if result.get("error") == "no_resume":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


class WorkflowTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        workflow = WorkflowService().get_execution(request.user, workflow_id)
        if workflow is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        items = WorkflowTimelineService().build_timeline(workflow)
        return Response(
            {
                "workflow_id": str(workflow.id),
                "items": items,
            }
        )


class WorkflowMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        result = WorkflowChatService().list_messages(request.user, workflow_id)
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)

    def post(self, request, workflow_id):
        serializer = WorkflowPostMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = WorkflowChatService().post_message(
            request.user,
            workflow_id,
            content=serializer.validated_data["content"],
        )
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if result.get("error") == "empty":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        if result.get("error") == "no_resume":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        if result.get("error") == "invalid":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


class WorkflowActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = WorkflowChatService().execute_action(
            request.user,
            workflow_id,
            action_key=data["action_key"],
            params=data.get("params") or {},
            confirmed=data.get("confirmed", False),
        )
        if result is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if result.get("error") == "confirmation_required":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        if result.get("error") == "no_resume":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        if result.get("error") == "invalid":
            return Response({"detail": result["detail"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)
