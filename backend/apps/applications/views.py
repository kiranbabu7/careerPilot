from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.interview_prep import InterviewPrepAgent
from apps.agents.serializers import AgentExecutionSerializer
from apps.applications.models import APPLICATION_STAGE_ORDER, ApplicationStage
from apps.applications.repositories import (
    ApplicationRepository,
    InterviewPlanRepository,
    InterviewRepository,
)
from apps.applications.serializers import (
    ApplicationDetailSerializer,
    ApplicationListSerializer,
    ApplicationUpdateSerializer,
    InterviewCreateSerializer,
    InterviewDetailSerializer,
    InterviewListResponseSerializer,
    InterviewPlanDetailSerializer,
    InterviewUpdateSerializer,
)
from apps.applications.services import ApplicationActivityService, InterviewService
from apps.jobs.repositories import OpportunityRepository
from apps.resumes.models import ApplicationMaterial


def _annotate_material_flags(applications: list) -> None:
    if not applications:
        return
    opportunity_ids = [app.opportunity_id for app in applications]
    material_types: dict = {}
    for row in (
        ApplicationMaterial.objects.filter(opportunity_id__in=opportunity_ids)
        .values("opportunity_id", "material_type")
        .distinct()
    ):
        oid = row["opportunity_id"]
        material_types.setdefault(oid, set()).add(row["material_type"])
    for app in applications:
        app._material_types = material_types.get(app.opportunity_id, set())


class ApplicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        repo = ApplicationRepository()
        grouped = repo.list_by_stage(request.user)
        all_apps = [app for apps in grouped.values() for app in apps]
        _annotate_material_flags(all_apps)

        stages = {
            stage: ApplicationListSerializer(
                grouped.get(stage, []), many=True
            ).data
            for stage in APPLICATION_STAGE_ORDER
        }
        return Response(
            {
                "stage_order": [s.value for s in APPLICATION_STAGE_ORDER],
                "stages": stages,
            }
        )


class ApplicationForOpportunityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, opportunity_id):
        application = ApplicationRepository().get_for_opportunity(
            request.user, opportunity_id
        )
        if application is None:
            return Response({"application": None})
        _annotate_material_flags([application])
        return Response(
            {
                "application": ApplicationListSerializer(application).data,
            }
        )


class ApplicationCreateFromOpportunityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        application, created = ApplicationRepository().create_from_opportunity(
            request.user,
            opportunity,
        )
        _annotate_material_flags([application])
        if created:
            ApplicationActivityService().record_application_created(
                request.user, application
            )

        return Response(
            {
                "application": ApplicationDetailSerializer(
                    application, context={"user": request.user}
                ).data,
                "created": created,
            },
            status=201 if created else 200,
        )


class ApplicationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, application_id):
        application = ApplicationRepository().get_for_user(
            request.user, application_id
        )
        if application is None:
            return Response({"detail": "Not found."}, status=404)
        _annotate_material_flags([application])
        serializer = ApplicationDetailSerializer(
            application, context={"user": request.user}
        )
        return Response(serializer.data)

    def patch(self, request, application_id):
        application = ApplicationRepository().get_for_user(
            request.user, application_id
        )
        if application is None:
            return Response({"detail": "Not found."}, status=404)

        serializer = ApplicationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        previous_stage = application.stage

        updated = ApplicationRepository().update(
            application,
            stage=data.get("stage"),
            notes=data.get("notes"),
            priority=data.get("priority"),
            target_follow_up_at=data.get("target_follow_up_at"),
            stage_notes=data.get("stage_notes", ""),
        )

        if data.get("stage") and data["stage"] != previous_stage:
            ApplicationActivityService().record_stage_changed(
                request.user, updated, previous_stage
            )

        _annotate_material_flags([updated])
        return Response(
            ApplicationDetailSerializer(updated, context={"user": request.user}).data
        )


class ApplicationInterviewPrepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id):
        application = ApplicationRepository().get_for_user(
            request.user, application_id
        )
        if application is None:
            return Response({"detail": "Not found."}, status=404)

        agent = InterviewPrepAgent()
        result = agent.generate(
            request.user,
            application.opportunity,
            application=application,
        )
        ApplicationActivityService().record_interview_prep_generated(
            request.user, result["plan"], application=application
        )

        return Response(
            {
                "application": ApplicationListSerializer(application).data,
                "interview_plan": InterviewPlanDetailSerializer(result["plan"]).data,
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )


class InterviewListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        interviews = InterviewRepository().list_for_user(request.user)
        upcoming_interviews = [
            interview
            for interview in interviews
            if interview.scheduled_at and interview.scheduled_at >= now
            and interview.outcome in ("scheduled", "completed")
        ]
        upcoming_interviews.sort(key=lambda item: item.scheduled_at)

        plans = InterviewPlanRepository().list_for_user(request.user)
        active: list = []
        upcoming_prep: list = []
        recent: list = []

        for plan in plans:
            stage = plan.application.stage if plan.application else None
            if stage in (
                ApplicationStage.INTERVIEWING,
                ApplicationStage.APPLIED,
                ApplicationStage.OFFER,
            ):
                active.append(plan)
            elif plan.status == "completed" and len(upcoming_prep) < 5:
                upcoming_prep.append(plan)
            else:
                recent.append(plan)

        if not upcoming_prep and plans:
            upcoming_prep = plans[:3]
        if not recent:
            recent = plans[:10]

        return Response(
            InterviewListResponseSerializer(
                {
                    "upcoming_interviews": upcoming_interviews[:20],
                    "active": active[:20],
                    "upcoming": upcoming_prep[:10],
                    "recent": recent[:20],
                }
            ).data
        )

    def post(self, request):
        serializer = InterviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            interview = InterviewService().create_external(
                request.user,
                serializer.validated_data,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            InterviewDetailSerializer(interview).data,
            status=status.HTTP_201_CREATED,
        )


class InterviewDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_interview(self, user, interview_id):
        return InterviewRepository().get_for_user(user, interview_id)

    def _get_plan(self, user, interview_id):
        return InterviewPlanRepository().get_for_user(user, interview_id)

    def get(self, request, interview_id):
        interview = self._get_interview(request.user, interview_id)
        if interview is not None:
            return Response(InterviewDetailSerializer(interview).data)

        plan = self._get_plan(request.user, interview_id)
        if plan is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(InterviewPlanDetailSerializer(plan).data)

    def patch(self, request, interview_id):
        interview = self._get_interview(request.user, interview_id)
        if interview is None:
            return Response({"detail": "Not found."}, status=404)

        serializer = InterviewUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = InterviewService().update(
            request.user,
            interview_id,
            serializer.validated_data,
        )
        return Response(InterviewDetailSerializer(updated).data)


class InterviewInterviewPrepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, interview_id):
        interview = InterviewRepository().get_for_user(request.user, interview_id)
        if interview is None:
            return Response({"detail": "Not found."}, status=404)

        agent = InterviewPrepAgent()
        result = agent.generate(
            request.user,
            interview.opportunity,
            application=interview.application,
            interview=interview,
        )
        ApplicationActivityService().record_interview_prep_generated(
            request.user,
            result["plan"],
            application=interview.application,
        )

        return Response(
            {
                "interview": InterviewDetailSerializer(interview).data,
                "interview_plan": InterviewPlanDetailSerializer(result["plan"]).data,
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )
