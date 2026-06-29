"""Agent execution and decision persistence."""

from django.db.models import Q

from apps.agents.models import AgentExecution, DecisionRecommendation


class AgentExecutionRepository:
    def list_for_user(self, user) -> list[AgentExecution]:
        return list(
            AgentExecution.objects.filter(user=user).order_by("-created_at")
        )

    def get_for_user(self, user, execution_id) -> AgentExecution | None:
        return (
            AgentExecution.objects.filter(user=user, id=execution_id)
            .select_related("workflow_execution")
            .first()
        )

    def list_for_user_filtered(
        self,
        user,
        *,
        agent_name: str | None = None,
        status: str | None = None,
        workflow_id: str | None = None,
        started_after=None,
        started_before=None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AgentExecution], int]:
        qs = AgentExecution.objects.filter(user=user)

        if agent_name:
            qs = qs.filter(agent_name=agent_name)
        if status:
            qs = qs.filter(status=status)
        if workflow_id:
            qs = qs.filter(workflow_execution_id=workflow_id)
        if started_after:
            qs = qs.filter(created_at__gte=started_after)
        if started_before:
            qs = qs.filter(created_at__lte=started_before)
        if search:
            qs = qs.filter(
                Q(reasoning_summary__icontains=search)
                | Q(error_message__icontains=search)
                | Q(agent_name__icontains=search)
            )

        count = qs.count()
        results = list(
            qs.select_related("workflow_execution")
            .order_by("-created_at")[offset : offset + limit]
        )
        return results, count

    def create(self, user, **fields) -> AgentExecution:
        return AgentExecution.objects.create(user=user, **fields)

    def get_for_workflow(self, workflow, agent_name: str) -> AgentExecution | None:
        return (
            AgentExecution.objects.filter(
                workflow_execution=workflow,
                agent_name=agent_name,
            )
            .order_by("-created_at")
            .first()
        )


class DecisionRecommendationRepository:
    def create(self, user, **fields) -> DecisionRecommendation:
        return DecisionRecommendation.objects.create(user=user, **fields)

    def get_for_user(self, user, recommendation_id) -> DecisionRecommendation | None:
        return (
            DecisionRecommendation.objects.filter(user=user, id=recommendation_id)
            .select_related("agent_execution", "workflow_execution")
            .first()
        )

    def list_for_user(
        self,
        user,
        *,
        workflow_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DecisionRecommendation], int]:
        qs = DecisionRecommendation.objects.filter(user=user)
        if workflow_id:
            qs = qs.filter(workflow_execution_id=workflow_id)
        count = qs.count()
        results = list(
            qs.select_related("agent_execution", "workflow_execution")
            .order_by("-created_at")[offset : offset + limit]
        )
        return results, count

    def get_latest_for_user(self, user) -> DecisionRecommendation | None:
        return (
            DecisionRecommendation.objects.filter(user=user)
            .select_related("agent_execution", "workflow_execution")
            .order_by("-created_at")
            .first()
        )
