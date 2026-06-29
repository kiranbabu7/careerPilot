"""Workflow chat refinement — messages and confirmed actions."""

from __future__ import annotations

import hashlib
import json
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.agents.company_research import CompanyResearchAgent
from apps.agents.cover_letter import CoverLetterAgent
from apps.workflows.langchain_tools import invoke_workflow_tool
from apps.agents.material_context import NoActiveResumeError
from apps.agents.resume_tailoring import ResumeTailorAgent
from apps.agents.serializers import AgentExecutionSerializer
from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD, HIGH_MATCH_THRESHOLD
from apps.jobs.models import OpportunityStatus
from apps.jobs.repositories import JobRepository, OpportunityRepository
from apps.jobs.serializers import OpportunitySerializer
from apps.applications.models import ApplicationStage
from apps.applications.repositories import ApplicationRepository
from apps.resumes.serializers import ApplicationMaterialSerializer
from apps.workflows.follow_up import (
    FOLLOW_UP_ADJUST_THRESHOLD,
    FOLLOW_UP_COVER_LETTER,
    FOLLOW_UP_GENERATE_DECISION,
    FOLLOW_UP_HELP,
    FOLLOW_UP_INTERVIEW_PREP,
    FOLLOW_UP_VIEW_INTERVIEW_PREP,
    FOLLOW_UP_VIEW_TAILORED_RESUME,
    FOLLOW_UP_DOWNLOAD_TAILORED_RESUME,
    FOLLOW_UP_VIEW_COVER_LETTER,
    FOLLOW_UP_DOWNLOAD_COVER_LETTER,
    FOLLOW_UP_ADD_INTERVIEW,
    build_cover_letter_follow_up_actions,
    build_tailored_resume_follow_up_actions,
    build_view_interview_prep_action,
    FOLLOW_UP_LIST_APPLICATIONS,
    FOLLOW_UP_QUESTION,
    FOLLOW_UP_RERUN_SEARCH,
    FOLLOW_UP_RESEARCH_COMPANY,
    FOLLOW_UP_SHOW_BORDERLINE,
    FOLLOW_UP_SHOW_REJECTED,
    FOLLOW_UP_TAILOR_RESUME,
    FOLLOW_UP_UPDATE_STATUS,
    build_action_cards,
    build_assistant_reply,
    build_contextual_actions,
    classify_follow_up,
    is_affirmative_confirmation,
    should_enable_tailor_selection,
)
from apps.workflows.models import WorkflowExecutionStatus, WorkflowMessageRole
from apps.workflows.repositories import WorkflowMessageRepository, WorkflowRepository
from apps.workflows.serializers import WorkflowExecutionSerializer, WorkflowMessageSerializer
from apps.workflows.services import WorkflowService

logger = logging.getLogger(__name__)


def _json_safe(value):
    """Ensure nested serializer payloads can be stored in JSON fields."""
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _tailor_selection_message_metadata(workflow) -> dict:
    result = workflow.result or {}
    return {
        "tailor_selection": {
            "pending": True,
            "tailor_options": result.get("tailor_options"),
        }
    }


class WorkflowChatService:
    def __init__(
        self,
        workflow_repo: WorkflowRepository | None = None,
        message_repo: WorkflowMessageRepository | None = None,
        workflow_service: WorkflowService | None = None,
        opportunity_repo: OpportunityRepository | None = None,
        application_repo: ApplicationRepository | None = None,
    ):
        self.workflow_repo = workflow_repo or WorkflowRepository()
        self.message_repo = message_repo or WorkflowMessageRepository()
        self.workflow_service = workflow_service or WorkflowService()
        self.opportunity_repo = opportunity_repo or OpportunityRepository()
        self.application_repo = application_repo or ApplicationRepository()
        self.job_repo = JobRepository()

    def list_messages(self, user, workflow_id):
        workflow = self.workflow_repo.get_for_user(user, workflow_id)
        if workflow is None:
            return None
        messages = self.message_repo.list_for_workflow(user, workflow_id)
        return {
            "workflow_id": str(workflow.id),
            "messages": WorkflowMessageSerializer(messages, many=True).data,
        }

    def post_message(self, user, workflow_id, *, content: str) -> dict | None:
        workflow = self.workflow_repo.get_for_user(user, workflow_id)
        if workflow is None:
            return None

        content = content.strip()
        if not content:
            return {"error": "empty", "detail": "Message cannot be empty."}

        user_message = self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.USER,
            content=content,
        )

        if is_affirmative_confirmation(content):
            pending_message = self.message_repo.get_latest_assistant_with_actions(
                user, workflow_id
            )
            if pending_message and pending_message.actions:
                return self._confirm_pending_actions(
                    user,
                    workflow,
                    user_message,
                    pending_message,
                )

            assistant_message = self.message_repo.create(
                user=user,
                workflow=workflow,
                role=WorkflowMessageRole.ASSISTANT,
                content=(
                    "There is nothing waiting for confirmation. "
                    "Ask to tailor a resume, generate interview prep, list applications, "
                    "or rerun search first."
                ),
                actions=[],
            )
            return {
                "user_message": WorkflowMessageSerializer(user_message).data,
                "assistant_message": WorkflowMessageSerializer(assistant_message).data,
                "actions": [],
            }

        classification = classify_follow_up(content)
        intent = classification["intent"]
        params = classification["params"]
        routing_metadata = {
            "routing": {
                "follow_up_intent": intent,
                "params": params,
                "method": "rule_based",
            }
        }
        workflow_context = workflow.context or {}
        opportunities_summary = self._build_opportunities_summary(user, workflow)
        applications_summary = self._build_applications_summary(user)

        reply_text = build_assistant_reply(
            workflow,
            intent=intent,
            params=params,
            workflow_context=workflow_context,
            opportunities_summary=opportunities_summary,
            applications_summary=applications_summary,
        )

        tailor_selection_enabled = False
        if (
            intent == FOLLOW_UP_TAILOR_RESUME
            and should_enable_tailor_selection(workflow, workflow_context, params)
        ):
            self.workflow_service.enable_tailor_selection_from_chat(
                user,
                workflow,
                goal=workflow.goal or "",
            )
            workflow.refresh_from_db()
            tailor_selection_enabled = True
            reply_text = build_assistant_reply(
                workflow,
                intent=intent,
                params=params,
                workflow_context=workflow_context,
                opportunities_summary=opportunities_summary,
                applications_summary=applications_summary,
            )

        if intent == FOLLOW_UP_HELP:
            actions = build_contextual_actions(
                workflow,
                opportunities_summary,
                applications_summary,
                workflow_context=workflow_context,
            )
        elif intent == FOLLOW_UP_QUESTION:
            actions = build_contextual_actions(
                workflow,
                opportunities_summary,
                applications_summary,
                workflow_context=workflow_context,
            )[:2]
        elif intent == FOLLOW_UP_LIST_APPLICATIONS:
            actions = []
        else:
            actions = build_action_cards(
                workflow,
                intent=intent,
                params=params,
                workflow_context=workflow_context,
                opportunities_summary=opportunities_summary,
            )

        assistant_message = self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.ASSISTANT,
            content=reply_text,
            actions=actions,
            metadata={
                **routing_metadata,
                **(
                    _tailor_selection_message_metadata(workflow)
                    if tailor_selection_enabled
                    else {}
                ),
            },
        )

        response = {
            "user_message": WorkflowMessageSerializer(user_message).data,
            "assistant_message": WorkflowMessageSerializer(assistant_message).data,
            "actions": actions,
        }
        if tailor_selection_enabled:
            response["workflow"] = WorkflowExecutionSerializer(workflow).data
        return response

    def seed_welcome_message(self, user, workflow):
        """Seed one assistant welcome message with contextual actions when chat is empty."""
        existing = self.message_repo.list_for_workflow(user, workflow.id)
        if any(msg.role == WorkflowMessageRole.ASSISTANT for msg in existing):
            return None

        opportunities_summary = self._build_opportunities_summary(user, workflow)
        applications_summary = self._build_applications_summary(user)
        workflow_context = workflow.context or {}
        actions = build_contextual_actions(
            workflow,
            opportunities_summary,
            applications_summary,
            workflow_context=workflow_context,
        )
        content = self._build_welcome_text(workflow)
        result = workflow.result or {}
        welcome_metadata = (
            _tailor_selection_message_metadata(workflow)
            if result.get("tailor_selection_pending")
            and not result.get("tailored_material_id")
            else {}
        )

        return self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.ASSISTANT,
            content=content,
            actions=actions,
            metadata=welcome_metadata,
        )

    def _build_welcome_text(self, workflow) -> str:
        result = workflow.result or {}
        next_action = (result.get("next_action") or "").strip()

        if result.get("tailor_selection_pending") and not result.get("tailored_material_id"):
            return (
                "Pick a role below to tailor your resume, or choose an action below."
            )

        if next_action:
            return (
                f"{next_action} Pick an action below for common next steps, "
                "or ask me a question."
            )
        return (
            f"Your workflow '{workflow.name}' is complete. "
            "Pick an action below or ask me a question."
        )

    def _confirm_pending_actions(
        self,
        user,
        workflow,
        user_message,
        pending_message,
    ) -> dict:
        """Execute all pending action cards after the user confirms via text."""
        actions_to_run = list(pending_message.actions)
        self.message_repo.update_actions(pending_message, [])

        summaries: list[str] = []
        assistant_replies: list[str] = []
        payloads: list[dict] = []
        follow_up_actions: list[dict] = []
        message_metadata: dict = {}

        for action in actions_to_run:
            try:
                result = self._dispatch_action(
                    user,
                    workflow,
                    action["key"],
                    action.get("params") or {},
                )
            except NoActiveResumeError as exc:
                return {
                    "user_message": WorkflowMessageSerializer(user_message).data,
                    "error": "no_resume",
                    "detail": str(exc),
                }
            except ValueError as exc:
                return {
                    "user_message": WorkflowMessageSerializer(user_message).data,
                    "error": "invalid",
                    "detail": str(exc),
                }
            except Exception:
                logger.exception(
                    "Workflow action %s failed during text confirmation for %s",
                    action.get("key"),
                    workflow.id,
                )
                raise

            summaries.append(result.get("summary", f"Completed action: {action['key']}"))
            assistant_replies.append(
                result.get("assistant_reply", result.get("summary", ""))
            )
            payloads.append(result.get("payload", {}))
            follow_up_actions.extend(result.get("follow_up_actions", []))
            action_metadata = result.get("message_metadata") or {}
            if action_metadata:
                message_metadata.update(action_metadata)

        system_content = " ".join(summaries)
        assistant_content = " ".join(reply for reply in assistant_replies if reply)

        system_message = self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.SYSTEM,
            content=system_content,
        )
        assistant_message = self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.ASSISTANT,
            content=assistant_content,
            actions=follow_up_actions,
            metadata=message_metadata,
        )

        workflow.refresh_from_db()

        return {
            "user_message": WorkflowMessageSerializer(user_message).data,
            "assistant_message": WorkflowMessageSerializer(assistant_message).data,
            "system_message": WorkflowMessageSerializer(system_message).data,
            "actions": follow_up_actions,
            "confirmed": True,
            "results": payloads,
            "workflow": WorkflowExecutionSerializer(workflow).data,
        }

    def execute_action(
        self,
        user,
        workflow_id,
        *,
        action_key: str,
        params: dict | None = None,
        confirmed: bool = False,
    ) -> dict | None:
        workflow = self.workflow_repo.get_for_user(user, workflow_id)
        if workflow is None:
            return None

        params = params or {}
        if not confirmed:
            return {
                "error": "confirmation_required",
                "detail": "Set confirmed=true to execute this action.",
            }

        try:
            result = self._dispatch_action(user, workflow, action_key, params)
        except NoActiveResumeError as exc:
            return {"error": "no_resume", "detail": str(exc)}
        except ValueError as exc:
            return {"error": "invalid", "detail": str(exc)}
        except Exception:
            logger.exception("Workflow action %s failed for %s", action_key, workflow_id)
            raise

        self._clear_executed_action(user, workflow.id, action_key, params)

        system_content = result.get("summary", f"Completed action: {action_key}")
        system_message = self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.SYSTEM,
            content=system_content,
        )

        assistant_message = self.message_repo.create(
            user=user,
            workflow=workflow,
            role=WorkflowMessageRole.ASSISTANT,
            content=result.get("assistant_reply", system_content),
            actions=result.get("follow_up_actions", []),
            metadata=result.get("message_metadata") or {},
        )

        workflow.refresh_from_db()

        return {
            "action_key": action_key,
            "result": result.get("payload", {}),
            "system_message": WorkflowMessageSerializer(system_message).data,
            "assistant_message": WorkflowMessageSerializer(assistant_message).data,
            "workflow": WorkflowExecutionSerializer(workflow).data,
        }

    def _clear_executed_action(self, user, workflow_id, action_key: str, params: dict) -> None:
        messages = self.message_repo.list_for_workflow(user, workflow_id)
        for message in reversed(messages):
            if message.role != WorkflowMessageRole.ASSISTANT or not message.actions:
                continue

            remaining = [
                action
                for action in message.actions
                if not (
                    action.get("key") == action_key
                    and (action.get("params") or {}) == params
                )
            ]
            if len(remaining) != len(message.actions):
                self.message_repo.update_actions(message, remaining)
                return

    def _dispatch_action(self, user, workflow, action_key: str, params: dict) -> dict:
        if action_key == FOLLOW_UP_RERUN_SEARCH:
            return self._action_rerun_search(user, workflow, params)
        if action_key == FOLLOW_UP_ADJUST_THRESHOLD:
            return self._action_adjust_threshold(workflow, params)
        if action_key == FOLLOW_UP_SHOW_BORDERLINE:
            return self._action_show_borderline(workflow, params)
        if action_key == FOLLOW_UP_SHOW_REJECTED:
            return self._action_show_rejected(workflow, params)
        if action_key == FOLLOW_UP_TAILOR_RESUME:
            return self._action_tailor_resume(user, workflow, params)
        if action_key == FOLLOW_UP_COVER_LETTER:
            return self._action_cover_letter(user, workflow, params)
        if action_key == FOLLOW_UP_RESEARCH_COMPANY:
            return self._action_research_company(user, workflow, params)
        if action_key == FOLLOW_UP_UPDATE_STATUS:
            return self._action_update_status(user, workflow, params)
        if action_key == FOLLOW_UP_GENERATE_DECISION:
            return self._action_generate_decision(user, workflow)
        if action_key == FOLLOW_UP_INTERVIEW_PREP:
            return self._action_interview_prep(user, workflow, params)
        if action_key == FOLLOW_UP_ADD_INTERVIEW:
            return self._action_add_interview(user, params)
        if action_key == FOLLOW_UP_VIEW_INTERVIEW_PREP:
            raise ValueError("View interview prep is a link action only.")
        if action_key in (
            FOLLOW_UP_VIEW_TAILORED_RESUME,
            FOLLOW_UP_DOWNLOAD_TAILORED_RESUME,
            FOLLOW_UP_VIEW_COVER_LETTER,
            FOLLOW_UP_DOWNLOAD_COVER_LETTER,
        ):
            raise ValueError("Material view/download are link actions only.")
        if action_key == FOLLOW_UP_LIST_APPLICATIONS:
            return self._action_list_applications(user, workflow, params)
        raise ValueError(f"Unsupported action: {action_key}")

    def _action_rerun_search(self, user, workflow, params: dict) -> dict:
        overrides = {k: v for k, v in params.items() if v is not None}
        payload = self.workflow_service.rerun_job_search(
            user,
            workflow.id,
            overrides=overrides or None,
        )
        if payload is None:
            raise ValueError("Workflow not found.")

        summary_bits = ["Job search rerun started — agents are running."]
        if overrides:
            summary_bits.append(f"Overrides: {overrides}")
        return {
            "summary": " ".join(summary_bits),
            "assistant_reply": (
                "Job search rerun is in progress. Watch the agent pipeline for live "
                "job search, company research, and evaluation updates."
            ),
            "payload": payload,
        }

    def _action_adjust_threshold(self, workflow, params: dict) -> dict:
        context = dict(workflow.context or {})
        refinement = dict(context.get("refinement") or {})
        current = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        target = params.get("high_match_threshold")
        if target is None:
            delta = params.get("delta", -10)
            target = max(BORDERLINE_MATCH_THRESHOLD, int(current) + int(delta))
        refinement["high_match_threshold"] = int(target)
        context["refinement"] = refinement
        workflow.context = context
        workflow.save(update_fields=["context", "updated_at"])

        opportunities = self.opportunity_repo.list_for_workflow_refinement(
            user=workflow.user,
            workflow=workflow,
            high_match_threshold=target,
            include_borderline=refinement.get("include_borderline", False),
            include_rejected=refinement.get("include_rejected", False),
        )

        return {
            "summary": f"Match threshold lowered to {target} for this workspace.",
            "assistant_reply": (
                f"Threshold override set to {target}. "
                f"{len(opportunities)} role(s) now qualify at this level."
            ),
            "payload": {
                "high_match_threshold": target,
                "visible_count": len(opportunities),
            },
        }

    def _action_show_borderline(self, workflow, params: dict) -> dict:
        context = dict(workflow.context or {})
        refinement = dict(context.get("refinement") or {})
        refinement["include_borderline"] = True
        context["refinement"] = refinement
        workflow.context = context
        workflow.save(update_fields=["context", "updated_at"])

        threshold = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        opportunities = self.opportunity_repo.list_for_workflow_refinement(
            user=workflow.user,
            workflow=workflow,
            include_borderline=True,
            include_rejected=refinement.get("include_rejected", False),
            high_match_threshold=threshold,
        )
        borderline = [
            o for o in opportunities
            if o.match_score is not None
            and BORDERLINE_MATCH_THRESHOLD <= o.match_score < threshold
        ]

        serialized = _json_safe(OpportunitySerializer(borderline[:10], many=True).data)
        return {
            "summary": f"Borderline roles surfaced ({len(borderline)}).",
            "assistant_reply": (
                f"Showing {len(borderline)} borderline role(s) for this workflow. "
                "Review them in Opportunities or ask for tailoring."
            ),
            "payload": {
                "borderline_count": len(borderline),
                "opportunities": serialized,
            },
            "message_metadata": {
                "refinement_result": {
                    "kind": "borderline",
                    "count": len(borderline),
                    "opportunities": serialized,
                }
            },
        }

    def _action_show_rejected(self, workflow, params: dict) -> dict:
        context = dict(workflow.context or {})
        refinement = dict(context.get("refinement") or {})
        refinement["include_rejected"] = True
        context["refinement"] = refinement
        workflow.context = context
        workflow.save(update_fields=["context", "updated_at"])

        threshold = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        opportunities = self.opportunity_repo.list_for_workflow_refinement(
            user=workflow.user,
            workflow=workflow,
            include_borderline=refinement.get("include_borderline", False),
            include_rejected=True,
            high_match_threshold=threshold,
        )
        rejected = [o for o in opportunities if o.status == OpportunityStatus.REJECTED]

        serialized = _json_safe(OpportunitySerializer(rejected[:10], many=True).data)
        return {
            "summary": f"Rejected roles surfaced ({len(rejected)}).",
            "assistant_reply": (
                f"Showing {len(rejected)} rejected role(s). "
                "Scores and evaluation gaps are available in each opportunity detail."
            ),
            "payload": {
                "rejected_count": len(rejected),
                "opportunities": serialized,
            },
            "message_metadata": {
                "refinement_result": {
                    "kind": "rejected",
                    "count": len(rejected),
                    "opportunities": serialized,
                }
            },
        }

    def _action_tailor_resume(self, user, workflow, params: dict) -> dict:
        workflow_context = workflow.context or {}
        if should_enable_tailor_selection(workflow, workflow_context, params):
            self.workflow_service.enable_tailor_selection_from_chat(
                user,
                workflow,
                goal=workflow.goal or "",
            )
            workflow.refresh_from_db()
            opportunities_summary = self._build_opportunities_summary(user, workflow)
            return {
                "summary": "Pick a role below to tailor your resume.",
                "assistant_reply": "Pick a role below to tailor your resume.",
                "payload": {
                    "tailor_selection_pending": True,
                    "tailor_options": workflow.result.get("tailor_options"),
                },
                "message_metadata": _tailor_selection_message_metadata(workflow),
                "follow_up_actions": build_action_cards(
                    workflow,
                    intent=FOLLOW_UP_TAILOR_RESUME,
                    params=params,
                    workflow_context=workflow_context,
                    opportunities_summary=opportunities_summary,
                ),
            }

        opportunity = self._resolve_pick(user, workflow, params)
        if opportunity is None:
            raise ValueError("No opportunity available for tailoring.")

        agent = ResumeTailorAgent()
        tailor_result = agent.tailor(user, opportunity, workflow=workflow)

        workflow.status = WorkflowExecutionStatus.COMPLETED
        workflow.completed_at = timezone.now()
        result = dict(workflow.result or {})
        material_id = str(tailor_result["material"].id)
        result["tailored_material_id"] = material_id
        result["selected_opportunity_id"] = str(opportunity.id)
        result["tailor_selection_pending"] = False
        workflow.result = result
        workflow.save()

        return {
            "summary": (
                f"Resume tailored for {opportunity.job.title} at {opportunity.job.company}."
            ),
            "assistant_reply": tailor_result["reasoning_summary"],
            "payload": {
                "opportunity": OpportunitySerializer(opportunity).data,
                "material": ApplicationMaterialSerializer(tailor_result["material"]).data,
                "agent_execution": AgentExecutionSerializer(tailor_result["execution"]).data,
            },
            "follow_up_actions": build_tailored_resume_follow_up_actions(material_id),
        }

    def _action_cover_letter(self, user, workflow, params: dict) -> dict:
        opportunity = self._resolve_pick(user, workflow, params)
        if opportunity is None:
            raise ValueError("No opportunity available for cover letter.")

        agent = CoverLetterAgent()
        letter_result = agent.generate(user, opportunity)

        workflow_result = dict(workflow.result or {})
        material_id = str(letter_result["material"].id)
        workflow_result["cover_letter_material_id"] = material_id
        workflow_result["selected_opportunity_id"] = str(opportunity.id)
        workflow.result = workflow_result
        workflow.save(update_fields=["result", "updated_at"])

        return {
            "summary": f"Cover letter generated for {opportunity.job.title}.",
            "assistant_reply": letter_result["reasoning_summary"],
            "payload": {
                "opportunity": OpportunitySerializer(opportunity).data,
                "material": ApplicationMaterialSerializer(letter_result["material"]).data,
                "agent_execution": AgentExecutionSerializer(letter_result["execution"]).data,
            },
            "follow_up_actions": build_cover_letter_follow_up_actions(material_id),
        }

    def _action_research_company(self, user, workflow, params: dict) -> dict:
        opportunity = self._resolve_company_for_research(user, workflow, params)
        if opportunity is None:
            company_name = params.get("company_name", "that company")
            raise ValueError(f"No opportunity available to research {company_name}.")

        agent = CompanyResearchAgent()
        result = agent.research(user, opportunity, workflow=workflow)
        opportunity.refresh_from_db()
        research = result.get("company_research") or {}
        company = opportunity.job.company

        assistant_reply = result["reasoning_summary"]
        if research.get("available"):
            summary = (research.get("summary") or "").strip()
            if summary:
                trimmed = summary if len(summary) <= 500 else f"{summary[:497]}..."
                assistant_reply = (
                    f"Research complete for {company}. {trimmed} "
                    "View full details on the Companies page."
                )

        follow_up_actions: list[dict] = []
        if research.get("available"):
            follow_up_actions.append(
                {
                    "key": "view_companies",
                    "label": "View Companies",
                    "description": "Open your company research dashboard.",
                    "params": {},
                    "requires_confirmation": False,
                    "endpoint_hint": "/companies",
                }
            )

        return {
            "summary": f"Company research completed for {company}.",
            "assistant_reply": assistant_reply,
            "payload": {
                "opportunity": OpportunitySerializer(opportunity).data,
                "company_research": research,
                "agent_execution": AgentExecutionSerializer(result["execution"]).data,
                "company_name": company,
            },
            "follow_up_actions": follow_up_actions,
        }

    def _action_update_status(self, user, workflow, params: dict) -> dict:
        opportunity = self._resolve_pick(user, workflow, params)
        status = params.get("status")
        if opportunity is None:
            raise ValueError("No opportunity available to update.")
        if not status:
            raise ValueError("status is required.")

        updated = self.opportunity_repo.update_status(opportunity, status)
        return {
            "summary": f"Marked {updated.job.title} as {status}.",
            "assistant_reply": f"Updated {updated.job.title} at {updated.job.company} to '{status}'.",
            "payload": {"opportunity": OpportunitySerializer(updated).data},
        }

    def _action_generate_decision(self, user, workflow) -> dict:
        context = workflow.context or {}
        tool_result = invoke_workflow_tool(
            self.workflow_service,
            user,
            workflow,
            "decision",
            context,
        )
        execution_id = tool_result.data.get("decision_execution_id", "")
        return {
            "summary": "Decision recommendation generated.",
            "assistant_reply": tool_result.summary,
            "payload": {
                "agent_execution_id": execution_id,
                "reasoning_summary": tool_result.summary,
            },
        }

    def _action_add_interview(self, user, params: dict) -> dict:
        from apps.applications.services import InterviewService

        company = params.get("company")
        job_title = params.get("job_title")
        if not company or not job_title:
            raise ValueError("Company and job title are required to add an interview.")

        payload = {
            "company": company,
            "job_title": job_title,
            "round_label": params.get("round_label", ""),
            "interviewer_notes": params.get("interviewer_notes", ""),
            "format": params.get("format", "video"),
            "outcome": params.get("outcome", "scheduled"),
            "job_description": params.get("job_description", ""),
        }
        scheduled_at = self._parse_interview_datetime(params)
        if scheduled_at:
            payload["scheduled_at"] = scheduled_at

        interview = InterviewService().create_external(user, payload)
        job = interview.opportunity.job
        return {
            "summary": f"Interview tracked for {job.title} at {job.company}.",
            "assistant_reply": (
                f"Added interview for {job.title} at {job.company}. "
                "Open the Interviews page to edit details or generate prep."
            ),
            "payload": {
                "interview_id": str(interview.id),
                "application_id": str(interview.application_id)
                if interview.application_id
                else None,
            },
            "follow_up_actions": [],
        }

    def _parse_interview_datetime(self, params: dict):
        from datetime import datetime

        from django.utils import timezone
        from django.utils.dateparse import parse_date, parse_datetime

        raw = params.get("scheduled_at") or params.get("scheduled_at_raw")
        if not raw:
            return None
        if hasattr(raw, "isoformat"):
            return raw
        if not isinstance(raw, str):
            return None

        parsed = parse_datetime(raw)
        if parsed is None:
            date_only = parse_date(raw)
            if date_only:
                parsed = datetime.combine(date_only, datetime.min.time())
        if parsed and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed

    def _action_interview_prep(self, user, workflow, params: dict) -> dict:
        goal = params.get("goal") or workflow.goal or "Interview prep for active applications"
        context = {**(workflow.context or {}), "goal": goal}
        tool_result = invoke_workflow_tool(
            self.workflow_service,
            user,
            workflow,
            "interview_prep",
            context,
        )
        plan_id = tool_result.data.get("interview_plan_id")
        result = {
            "summary": tool_result.summary,
            "assistant_reply": (
                f"{tool_result.summary} Use View prep plan below to open your full "
                "roadmap and practice questions."
            ),
            "payload": {
                "opportunity_id": tool_result.data.get("selected_opportunity_id"),
                "interview_plan_id": plan_id,
                "interview_prep_target_source": tool_result.data.get(
                    "interview_prep_target_source"
                ),
            },
        }
        if plan_id:
            result["follow_up_actions"] = [build_view_interview_prep_action(plan_id)]
        return result

    def _action_list_applications(self, user, workflow, params: dict) -> dict:
        applications_summary = self._build_applications_summary(user)
        applications = list(applications_summary.get("applications") or [])
        stage_filter = params.get("stage_filter")
        if stage_filter == "interviewing":
            applications = [
                app for app in applications if app.get("stage") == "interviewing"
            ]
        elif stage_filter == "active":
            applications = [
                app
                for app in applications
                if app.get("stage") not in ("rejected", "withdrawn")
            ]

        assistant_reply = build_assistant_reply(
            workflow,
            intent=FOLLOW_UP_LIST_APPLICATIONS,
            params=params,
            workflow_context=workflow.context or {},
            opportunities_summary=self._build_opportunities_summary(user, workflow),
            applications_summary=applications_summary,
        )
        return {
            "summary": f"Listed {len(applications)} application(s).",
            "assistant_reply": assistant_reply,
            "payload": {
                "application_count": len(applications),
                "applications": applications[:10],
            },
        }

    def _resolve_pick(self, user, workflow, params: dict):
        pick = params.get("pick", "best")
        refinement = (workflow.context or {}).get("refinement") or {}
        threshold = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        opportunities = self.opportunity_repo.list_for_workflow_refinement(
            user,
            workflow,
            include_borderline=refinement.get("include_borderline", False),
            include_rejected=refinement.get("include_rejected", False),
            high_match_threshold=threshold,
        )
        if not opportunities and pick == "best":
            opportunities = self.opportunity_repo.list_for_user(
                user,
                include_rejected=True,
                include_low_match=True,
            )
        if not opportunities:
            return None
        if pick == "best":
            return opportunities[0]
        opportunity_id = params.get("opportunity_id")
        if opportunity_id:
            return self.opportunity_repo.get_for_user(user, opportunity_id)
        return opportunities[0]

    def _resolve_company_for_research(self, user, workflow, params: dict):
        company_name = (params.get("company_name") or "").strip()
        if not company_name:
            return self._resolve_pick(user, workflow, params)

        normalized_target = company_name.lower()
        refinement = (workflow.context or {}).get("refinement") or {}
        threshold = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)

        for opportunities in (
            self.opportunity_repo.list_for_workflow_refinement(
                user,
                workflow,
                include_rejected=True,
                include_borderline=True,
                high_match_threshold=threshold,
            ),
            self.opportunity_repo.list_for_user(
                user,
                include_rejected=True,
                include_low_match=True,
            ),
        ):
            match = self._match_opportunity_by_company(opportunities, normalized_target)
            if match is not None:
                return match

        return self._create_research_opportunity(user, workflow, company_name)

    def _match_opportunity_by_company(self, opportunities, normalized_target: str):
        exact_matches = []
        partial_matches = []
        for opportunity in opportunities:
            company_norm = " ".join((opportunity.job.company or "").lower().split())
            if not company_norm:
                continue
            if company_norm == normalized_target:
                exact_matches.append(opportunity)
            elif normalized_target in company_norm or company_norm in normalized_target:
                partial_matches.append(opportunity)

        if exact_matches:
            return max(exact_matches, key=lambda opp: opp.match_score or 0)
        if partial_matches:
            return max(partial_matches, key=lambda opp: opp.match_score or 0)
        return None

    def _create_research_opportunity(self, user, workflow, company_name: str):
        dedupe_raw = f"research:{company_name.lower()}"
        dedupe_key = hashlib.sha256(dedupe_raw.encode()).hexdigest()

        job = self.job_repo.get_by_dedupe_key(dedupe_key)
        if job is None:
            job = self.job_repo.create(
                source="company_research",
                title="Company research",
                company=company_name,
                description=f"On-demand company research for {company_name}.",
                dedupe_key=dedupe_key,
            )

        opportunity, _created = self.opportunity_repo.get_or_create_for_user_job(
            user,
            job,
            workflow=workflow,
            defaults={
                "status": OpportunityStatus.SAVED,
                "source_agent": "company_research",
                "match_context": f"On-demand research request for {company_name}.",
            },
        )
        if opportunity.workflow_execution_id != workflow.id:
            opportunity.workflow_execution = workflow
            opportunity.save(update_fields=["workflow_execution", "updated_at"])
        return opportunity

    def _build_opportunities_summary(self, user, workflow) -> dict:
        refinement = (workflow.context or {}).get("refinement") or {}
        threshold = refinement.get("high_match_threshold", HIGH_MATCH_THRESHOLD)
        workflow_ops = self.opportunity_repo.list_for_workflow_refinement(
            user,
            workflow,
            include_borderline=True,
            include_rejected=True,
            high_match_threshold=threshold,
        )
        best = workflow_ops[0] if workflow_ops else None
        rejected_samples = [
            o for o in workflow_ops if o.status == OpportunityStatus.REJECTED
        ][:3]

        return {
            "best_opportunity": (
                {
                    "id": str(best.id),
                    "title": best.job.title,
                    "company": best.job.company,
                    "match_score": best.match_score,
                }
                if best
                else None
            ),
            "sample_rejected": [
                {
                    "title": o.job.title,
                    "company": o.job.company,
                    "match_score": o.match_score,
                    "evaluation": o.evaluation,
                    "match_context": o.match_context,
                }
                for o in rejected_samples
            ],
        }

    def _build_applications_summary(self, user) -> dict:
        active_stages = {
            ApplicationStage.DRAFT,
            ApplicationStage.APPLIED,
            ApplicationStage.INTERVIEWING,
            ApplicationStage.OFFER,
        }
        stage_priority = {
            ApplicationStage.INTERVIEWING: 0,
            ApplicationStage.OFFER: 1,
            ApplicationStage.APPLIED: 2,
            ApplicationStage.DRAFT: 3,
        }
        applications = self.application_repo.list_for_user(user)
        active = [app for app in applications if app.stage in active_stages]
        active.sort(
            key=lambda app: (
                stage_priority.get(app.stage, 99),
                -(app.opportunity.match_score or 0),
            )
        )
        top_prep = active[0] if active else None
        return {
            "total_count": len(applications),
            "active_count": len(active),
            "interviewing_count": sum(
                1 for app in active if app.stage == ApplicationStage.INTERVIEWING
            ),
            "top_prep_target": (
                {
                    "id": str(top_prep.id),
                    "title": top_prep.opportunity.job.title,
                    "company": top_prep.opportunity.job.company,
                    "stage": top_prep.stage,
                    "match_score": top_prep.opportunity.match_score,
                }
                if top_prep
                else None
            ),
            "applications": [
                {
                    "id": str(app.id),
                    "title": app.opportunity.job.title,
                    "company": app.opportunity.job.company,
                    "stage": app.stage,
                    "match_score": app.opportunity.match_score,
                }
                for app in applications
            ],
        }
