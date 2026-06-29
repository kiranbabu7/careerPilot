"""Job Evaluation agent — scores opportunities against user preferences."""

from collections.abc import Callable

from django.utils import timezone

from apps.agents.models import AgentExecutionStatus
from apps.agents.repositories import AgentExecutionRepository
from apps.jobs.evaluation import (
    BORDERLINE_MATCH_THRESHOLD,
    HIGH_MATCH_THRESHOLD,
    evaluate_opportunity,
)
from apps.jobs.models import OpportunityStatus
from apps.jobs.repositories import OpportunityRepository
from apps.users.repositories import UserPreferenceRepository

JOB_EVALUATION_AGENT_NAME = "job_evaluation"


class JobEvaluationAgent:
    def __init__(
        self,
        opportunity_repo: OpportunityRepository | None = None,
        preference_repo: UserPreferenceRepository | None = None,
        agent_repo: AgentExecutionRepository | None = None,
    ):
        self.opportunity_repo = opportunity_repo or OpportunityRepository()
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.agent_repo = agent_repo or AgentExecutionRepository()

    def _resolve_preferences(self, user, context: dict | None) -> dict:
        preference, _ = self.preference_repo.get_or_create_for_user(user)
        prefs = context.get("preferences", {}) if context else {}
        if not prefs:
            prefs = {
                "target_roles": preference.target_roles,
                "target_locations": preference.target_locations,
                "remote_preference": preference.remote_preference,
                "skills": preference.skills,
                "salary_min": preference.salary_min,
                "salary_max": preference.salary_max,
            }
        return prefs

    def _evaluate_opportunity(
        self,
        user,
        opportunity,
        *,
        workflow=None,
        context: dict | None = None,
        execution_id: str | None = None,
    ) -> dict:
        """Score one opportunity without creating an AgentExecution record."""
        prefs = self._resolve_preferences(user, context)

        job = opportunity.job
        job.refresh_from_db()
        result = evaluate_opportunity(
            job_title=job.title,
            job_description=job.description,
            job_location=job.location,
            is_remote=job.is_remote,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            company_research=job.company_research or {},
            preferences=prefs,
            planner_constraints=(context or {}).get("planner_constraints"),
        )

        evaluation_payload = dict(result)
        if execution_id:
            evaluation_payload["agent_execution_id"] = execution_id

        self.opportunity_repo.update_evaluation(
            opportunity,
            match_score=result["match_score"],
            evaluation=evaluation_payload,
        )

        if opportunity.status == OpportunityStatus.DISCOVERED:
            if result["match_score"] < BORDERLINE_MATCH_THRESHOLD:
                self.opportunity_repo.update_status(
                    opportunity, OpportunityStatus.REJECTED
                )
        opportunity.refresh_from_db()

        reasoning = (
            f"Evaluated '{job.title}' at {job.company}: "
            f"score {result['match_score']}/100 ({result['recommendation'].replace('_', ' ')})."
        )

        return {
            "opportunity": opportunity,
            "opportunity_id": str(opportunity.id),
            "job_title": job.title,
            "company": job.company,
            "match_score": result["match_score"],
            "recommendation": result["recommendation"],
            "evaluation": result,
            "reasoning_summary": reasoning,
        }

    def evaluate(self, user, opportunity, *, workflow=None, context: dict | None = None) -> dict:
        started_at = timezone.now()
        workflow = workflow or opportunity.workflow_execution
        job = opportunity.job
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=JOB_EVALUATION_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "opportunity_id": str(opportunity.id),
                "job_title": job.title,
            },
            started_at=started_at,
        )

        try:
            outcome = self._evaluate_opportunity(
                user,
                opportunity,
                workflow=workflow,
                context=context,
                execution_id=str(execution.id),
            )

            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "opportunity_id": outcome["opportunity_id"],
                "match_score": outcome["match_score"],
                "recommendation": outcome["recommendation"],
                "duration_ms": duration_ms,
            }
            execution.reasoning_summary = outcome["reasoning_summary"]
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                **outcome,
            }
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise

    def evaluate_batch(
        self,
        user,
        opportunities: list,
        *,
        workflow=None,
        context: dict | None = None,
        on_progress: Callable[[object, dict], None] | None = None,
    ) -> dict:
        """Evaluate multiple opportunities under a single AgentExecution."""
        if not opportunities:
            return {
                "execution": None,
                "evaluated_count": 0,
                "accepted_count": 0,
                "borderline_count": 0,
                "rejected_count": 0,
                "top_match_score": 0,
                "results": [],
            }

        started_at = timezone.now()
        workflow = workflow or opportunities[0].workflow_execution
        execution = self.agent_repo.create(
            user=user,
            workflow_execution=workflow,
            agent_name=JOB_EVALUATION_AGENT_NAME,
            status=AgentExecutionStatus.RUNNING,
            input_data={
                "opportunity_ids": [str(opportunity.id) for opportunity in opportunities],
                "batch_size": len(opportunities),
            },
            started_at=started_at,
        )
        execution_id = str(execution.id)

        results = []
        accepted_count = 0
        borderline_count = 0
        rejected_count = 0
        top_score = 0

        try:
            for opportunity in opportunities:
                outcome = self._evaluate_opportunity(
                    user,
                    opportunity,
                    workflow=workflow,
                    context=context,
                    execution_id=execution_id,
                )
                results.append(outcome)
                score = outcome["match_score"]
                top_score = max(top_score, score)
                if score >= HIGH_MATCH_THRESHOLD:
                    accepted_count += 1
                elif score >= BORDERLINE_MATCH_THRESHOLD:
                    borderline_count += 1
                else:
                    rejected_count += 1
                if on_progress:
                    on_progress(opportunity, outcome)

            completed_at = timezone.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            evaluated_count = len(results)
            reasoning = (
                f"Evaluated {evaluated_count} role{'s' if evaluated_count != 1 else ''}: "
                f"{accepted_count} strong match{'es' if accepted_count != 1 else ''}, "
                f"top score {top_score}/100."
            )

            execution.status = AgentExecutionStatus.COMPLETED
            execution.output_data = {
                "evaluated_count": evaluated_count,
                "accepted_count": accepted_count,
                "borderline_count": borderline_count,
                "rejected_count": rejected_count,
                "top_match_score": top_score,
                "duration_ms": duration_ms,
                "results": [
                    {
                        "opportunity_id": item["opportunity_id"],
                        "job_title": item["job_title"],
                        "company": item["company"],
                        "match_score": item["match_score"],
                        "recommendation": item["recommendation"],
                    }
                    for item in results
                ],
            }
            execution.reasoning_summary = reasoning
            execution.completed_at = completed_at
            execution.save()

            return {
                "execution": execution,
                "evaluated_count": evaluated_count,
                "accepted_count": accepted_count,
                "borderline_count": borderline_count,
                "rejected_count": rejected_count,
                "top_match_score": top_score,
                "results": results,
            }
        except Exception as exc:
            completed_at = timezone.now()
            execution.status = AgentExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = completed_at
            execution.save()
            raise
