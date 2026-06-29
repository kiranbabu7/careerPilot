from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.company_research import CompanyResearchAgent
from apps.agents.cover_letter import CoverLetterAgent
from apps.agents.interview_prep import InterviewPrepAgent
from apps.agents.job_evaluation import JobEvaluationAgent
from apps.agents.material_context import NoActiveResumeError
from apps.agents.resume_tailoring import ResumeTailorAgent
from apps.agents.serializers import AgentExecutionSerializer
from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD, HIGH_MATCH_THRESHOLD
from apps.jobs.repositories import OpportunityRepository
from apps.jobs.serializers import (
    OpportunityListSerializer,
    OpportunitySerializer,
    OpportunityStatusUpdateSerializer,
)
from apps.applications.serializers import InterviewPlanDetailSerializer
from apps.applications.services import ApplicationActivityService
from apps.resumes.repositories import ApplicationMaterialRepository
from apps.resumes.serializers import ApplicationMaterialSerializer
from apps.users.repositories import UserPreferenceRepository


class JobScheduleStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference, _ = UserPreferenceRepository().get_or_create_for_user(request.user)
        last_run_summary = preference.last_schedule_message or ""
        if not last_run_summary and preference.last_scheduled_run_at:
            workflows = request.user.workflow_executions.filter(
                context__trigger="scheduled",
                completed_at__isnull=False,
            ).order_by("-completed_at")
            latest = workflows.first()
            if latest and latest.result:
                discovered = latest.result.get("discovered_count", 0)
                evaluated = latest.result.get("evaluated_count", 0)
                last_run_summary = (
                    f"Discovered {discovered} roles; evaluated {evaluated}."
                )

        return Response(
            {
                "enabled": preference.job_search_schedule_enabled,
                "interval_minutes": preference.job_search_schedule_interval_minutes,
                "last_run_at": preference.last_scheduled_run_at,
                "next_run_at": preference.next_scheduled_run_at,
                "last_job_search_at": preference.last_job_search_at,
                "last_run_summary": last_run_summary,
            }
        )


class OpportunityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        include_rejected = request.query_params.get("include_rejected", "").lower() in (
            "1",
            "true",
            "yes",
        )
        include_low_match = request.query_params.get(
            "include_low_match", ""
        ).lower() in ("1", "true", "yes")
        workflow_id = request.query_params.get("workflow_id")
        filter_mode = (request.query_params.get("filter") or "").lower()

        repo = OpportunityRepository()
        workflow_execution_id = None

        if workflow_id:
            from apps.workflows.repositories import WorkflowRepository

            workflow = WorkflowRepository().get_for_user(request.user, workflow_id)
            if workflow is None:
                return Response({"detail": "Workflow not found."}, status=404)

            workflow_execution_id = str(workflow.id)
            include_borderline = filter_mode in ("all", "borderline")
            if filter_mode == "rejected":
                include_rejected = True
            elif filter_mode == "all":
                include_rejected = include_rejected or True
            opportunities = repo.list_for_workflow_refinement(
                request.user,
                workflow,
                include_rejected=include_rejected,
                include_borderline=include_borderline,
            )
        else:
            opportunities = repo.list_for_user(
                request.user,
                include_rejected=include_rejected,
                include_low_match=include_low_match,
            )

        serializer = OpportunityListSerializer(opportunities, many=True)
        return Response(
            {
                "high_match_threshold": HIGH_MATCH_THRESHOLD,
                "borderline_match_threshold": BORDERLINE_MATCH_THRESHOLD,
                "pending_evaluation_count": repo.count_unevaluated_for_user(
                    request.user
                ),
                "last_search_summary": repo.get_last_search_summary(request.user),
                "workflow_execution_id": workflow_execution_id,
                "opportunities": serializer.data,
            }
        )


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

    def patch(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        serializer = OpportunityStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = OpportunityRepository().update_status(
            opportunity, serializer.validated_data["status"]
        )
        return Response(OpportunitySerializer(updated).data)


class OpportunityResearchCompanyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        agent = CompanyResearchAgent()
        result = agent.research(request.user, opportunity)

        opportunity.refresh_from_db()
        opportunity.job.refresh_from_db()

        return Response(
            {
                "opportunity": OpportunitySerializer(opportunity).data,
                "company_research": result["company_research"],
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )


class OpportunityEvaluateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        agent = JobEvaluationAgent()
        result = agent.evaluate(request.user, opportunity)

        opportunity.refresh_from_db()

        return Response(
            {
                "opportunity": OpportunitySerializer(opportunity).data,
                "match_score": result["match_score"],
                "evaluation": result["evaluation"],
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )


class OpportunityTailorResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        agent = ResumeTailorAgent()
        try:
            result = agent.tailor(request.user, opportunity)
        except NoActiveResumeError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {
                "opportunity": OpportunitySerializer(opportunity).data,
                "material": ApplicationMaterialSerializer(result["material"]).data,
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )


class OpportunityCoverLetterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        agent = CoverLetterAgent()
        try:
            result = agent.generate(request.user, opportunity)
        except NoActiveResumeError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {
                "opportunity": OpportunitySerializer(opportunity).data,
                "material": ApplicationMaterialSerializer(result["material"]).data,
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )


class OpportunityMaterialsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        materials = ApplicationMaterialRepository().list_for_opportunity(
            request.user, opportunity_id
        )
        return Response(
            {
                "opportunity_id": str(opportunity.id),
                "materials": ApplicationMaterialSerializer(materials, many=True).data,
            }
        )


class OpportunityInterviewPrepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, opportunity_id):
        opportunity = OpportunityRepository().get_for_user(
            request.user, opportunity_id
        )
        if opportunity is None:
            return Response({"detail": "Not found."}, status=404)

        from apps.applications.repositories import ApplicationRepository

        application = ApplicationRepository().get_for_opportunity(
            request.user, opportunity_id
        )

        agent = InterviewPrepAgent()
        result = agent.generate(
            request.user,
            opportunity,
            application=application,
        )
        ApplicationActivityService().record_interview_prep_generated(
            request.user, result["plan"], application=application
        )

        return Response(
            {
                "opportunity": OpportunitySerializer(opportunity).data,
                "interview_plan": InterviewPlanDetailSerializer(result["plan"]).data,
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "reasoning_summary": result["reasoning_summary"],
            }
        )


class CompanyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        companies = OpportunityRepository().list_companies_for_user(request.user)
        return Response(companies)
