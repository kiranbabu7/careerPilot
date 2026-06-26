"""Workflow business logic."""

from django.utils import timezone

from apps.agents.job_search import JobSearchAgent
from apps.agents.planner import PlannerAgent
from apps.agents.serializers import AgentExecutionSerializer
from apps.memory.services import ActivityService, MemoryService
from apps.workflows.models import WorkflowExecutionStatus
from apps.workflows.repositories import WorkflowRepository
from apps.workflows.serializers import WorkflowExecutionSerializer


class WorkflowService:
    def __init__(
        self,
        repo: WorkflowRepository | None = None,
        planner: PlannerAgent | None = None,
        job_search_agent: JobSearchAgent | None = None,
        activity_service: ActivityService | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.repo = repo or WorkflowRepository()
        self.planner = planner or PlannerAgent()
        self.job_search_agent = job_search_agent or JobSearchAgent()
        self.activity_service = activity_service or ActivityService()
        self.memory_service = memory_service or MemoryService()

    def list_executions(self, user):
        return self.repo.list_for_user(user)

    def get_execution(self, user, workflow_id):
        for execution in self.repo.list_for_user(user):
            if str(execution.id) == str(workflow_id):
                return execution
        return None

    def start_workflow(self, user, *, goal: str) -> dict:
        goal = goal.strip()
        name = goal[:80] if len(goal) > 80 else goal or "Career goal"

        workflow = self.repo.create(
            user=user,
            name=name,
            goal=goal,
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        plan_result = self.planner.plan(user, workflow, goal)
        workflow.context = plan_result["context"]

        job_search_result = self.job_search_agent.search(
            user, workflow, plan_result["context"]
        )

        workflow.result = {
            "plan_summary": plan_result["plan_summary"],
            "suggested_steps": plan_result["suggested_steps"],
            "discovered_count": job_search_result["discovered_count"],
            "provider_summary": job_search_result["provider_summary"],
            "job_search_summary": job_search_result["reasoning_summary"],
        }
        workflow.status = WorkflowExecutionStatus.COMPLETED
        workflow.completed_at = timezone.now()
        workflow.save()

        self.activity_service.record_workflow_started(user, workflow)
        self.memory_service.record_workflow_context(
            user, workflow, plan_result["plan_summary"]
        )

        return {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "planner_execution": AgentExecutionSerializer(plan_result["execution"]).data,
            "job_search_execution": AgentExecutionSerializer(
                job_search_result["execution"]
            ).data,
            "plan_summary": plan_result["plan_summary"],
            "suggested_steps": plan_result["suggested_steps"],
            "discovered_count": job_search_result["discovered_count"],
            "provider_summary": job_search_result["provider_summary"],
            "job_search_summary": job_search_result["reasoning_summary"],
        }

    def rerun_job_search(self, user, workflow_id) -> dict:
        workflow = self.get_execution(user, workflow_id)
        if workflow is None:
            return None

        context = workflow.context or self.planner.build_context(user, workflow.goal)
        if not workflow.context:
            workflow.context = context
            workflow.save(update_fields=["context", "updated_at"])

        job_search_result = self.job_search_agent.search(user, workflow, context)

        existing_result = workflow.result or {}
        workflow.result = {
            **existing_result,
            "discovered_count": job_search_result["discovered_count"],
            "provider_summary": job_search_result["provider_summary"],
            "job_search_summary": job_search_result["reasoning_summary"],
        }
        workflow.save(update_fields=["result", "updated_at"])

        return {
            "workflow": WorkflowExecutionSerializer(workflow).data,
            "job_search_execution": AgentExecutionSerializer(
                job_search_result["execution"]
            ).data,
            "discovered_count": job_search_result["discovered_count"],
            "provider_summary": job_search_result["provider_summary"],
            "job_search_summary": job_search_result["reasoning_summary"],
        }
