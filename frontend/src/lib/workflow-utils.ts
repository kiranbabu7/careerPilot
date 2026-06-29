import { AGENT_LABELS } from "@/components/agents/agent-run-utils";

import type {
  AgentExecution,
  AgenticPlannerFields,
  IntentClassification,
  PlannerConstraint,
  PlannerToolStep,
  ReplanEvent,
  UserVisiblePlanStep,
  WorkflowActionCard,
  WorkflowDetail,
  WorkflowIntent,
  WorkflowMessage,
  WorkflowRefinementResultMetadata,
  WorkflowToolProgress,
  WorkflowToolProgressEvent,
} from "@/lib/api";



export const PIPELINE_TOOL_KEYS = [
  "job_search",
  "company_research",
  "job_evaluation",
  "resume_tailor",
  "cover_letter",
  "interview_prep",
] as const;

export type PipelineToolKey = (typeof PIPELINE_TOOL_KEYS)[number];

const REPLAN_ACTION_LABELS: Record<string, string> = {
  continue: "Continue plan",
  insert_tools: "Added tools",
  skip_tool: "Skipped tool",
  ask_user: "Needs your input",
  complete: "Plan complete",
  fail_with_reason: "Stopped",
};

function normalizeConstraints(raw: unknown): PlannerConstraint[] {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return Object.entries(raw as Record<string, unknown>)
      .filter(
        ([key, value]) =>
          key !== "requires_company_research" &&
          value != null &&
          String(value).trim().length > 0,
      )
      .map(([key, value]) => ({
        key,
        label: key.replace(/_/g, " "),
        value: typeof value === "string" ? value : String(value),
      }));
  }
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    .map((item) => ({
      key: typeof item.key === "string" ? item.key : "constraint",
      label: typeof item.label === "string" ? item.label : undefined,
      value: typeof item.value === "string" ? item.value : String(item.value ?? ""),
      source: typeof item.source === "string" ? item.source : undefined,
    }))
    .filter((item) => item.value.trim().length > 0);
}

function normalizeToolPlan(raw: unknown): PlannerToolStep[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    .map((item) => ({
      tool: typeof item.tool === "string" ? item.tool : "",
      why:
        typeof item.why === "string"
          ? item.why
          : typeof item.reason === "string"
            ? item.reason
            : "",
      auto_run: typeof item.auto_run === "boolean" ? item.auto_run : undefined,
      requires_confirmation:
        typeof item.requires_confirmation === "boolean"
          ? item.requires_confirmation
          : undefined,
      skipped: typeof item.skipped === "boolean" ? item.skipped : undefined,
      skip_reason: typeof item.skip_reason === "string" ? item.skip_reason : undefined,
      params:
        item.params && typeof item.params === "object"
          ? (item.params as Record<string, unknown>)
          : undefined,
      status:
        typeof item.status === "string"
          ? (item.status as PlannerToolStep["status"])
          : undefined,
    }))
    .filter((item) => item.tool.length > 0);
}

function normalizeUserVisiblePlan(raw: unknown): UserVisiblePlanStep[] {
  if (typeof raw === "string" && raw.trim()) {
    return [{ title: raw.trim() }];
  }
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    .map((item) => ({
      title: typeof item.title === "string" ? item.title : "Plan step",
      description: typeof item.description === "string" ? item.description : undefined,
    }));
}

function normalizeReplanEvents(raw: unknown): ReplanEvent[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    .map((item) => ({
      at: typeof item.at === "string" ? item.at : "",
      action: typeof item.action === "string" ? item.action : "continue",
      reason: typeof item.reason === "string" ? item.reason : "",
      trigger_tool: typeof item.trigger_tool === "string" ? item.trigger_tool : undefined,
      inserted_tools: Array.isArray(item.inserted_tools)
        ? item.inserted_tools.filter((tool): tool is string => typeof tool === "string")
        : undefined,
      skipped_tools: Array.isArray(item.skipped_tools)
        ? item.skipped_tools.filter((tool): tool is string => typeof tool === "string")
        : undefined,
    }))
    .filter((item) => item.reason.trim().length > 0);
}

function readAgenticFields(source: AgenticPlannerFields | Record<string, unknown> | undefined) {
  if (!source || typeof source !== "object") {
    return {
      constraints: [] as PlannerConstraint[],
      toolPlan: [] as PlannerToolStep[],
      successCriteria: [] as AgenticPlannerFields["success_criteria"],
      userVisiblePlan: [] as UserVisiblePlanStep[],
      planHistory: [] as AgenticPlannerFields["plan_history"],
      replanEvents: [] as ReplanEvent[],
      requiresConfirmation: undefined as boolean | undefined,
      reasoningSummary: undefined as string | undefined,
    };
  }

  const record = source as Record<string, unknown>;
  const successCriteria = Array.isArray(record.success_criteria)
    ? record.success_criteria
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
        .map((item) => ({
          description:
            typeof item.description === "string" ? item.description : String(item.description ?? ""),
          met: typeof item.met === "boolean" ? item.met : undefined,
        }))
        .filter((item) => item.description.trim().length > 0)
    : [];

  const planHistory = Array.isArray(record.plan_history)
    ? record.plan_history
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
        .map((item) => ({
          at: typeof item.at === "string" ? item.at : "",
          summary: typeof item.summary === "string" ? item.summary : "",
          tool_plan: normalizeToolPlan(item.tool_plan),
        }))
        .filter((item) => item.summary.trim().length > 0)
    : [];

  return {
    constraints: normalizeConstraints(record.constraints),
    toolPlan: normalizeToolPlan(record.tool_plan),
    successCriteria,
    userVisiblePlan: normalizeUserVisiblePlan(record.user_visible_plan),
    planHistory,
    replanEvents: normalizeReplanEvents(record.replan_events),
    requiresConfirmation:
      typeof record.requires_confirmation === "boolean"
        ? record.requires_confirmation
        : undefined,
    reasoningSummary:
      typeof record.reasoning_summary === "string" ? record.reasoning_summary : undefined,
  };
}

/** Resolve agentic planner data from WorkflowDetail top-level fields or workflow.result. */
export function resolveAgenticPlannerData(detail: WorkflowDetail | null) {
  if (!detail) return null;

  const fromDetail = readAgenticFields(detail);
  const fromResult = readAgenticFields(detail.workflow.result);

  const merged = {
    constraints: fromDetail.constraints.length > 0 ? fromDetail.constraints : fromResult.constraints,
    toolPlan: fromDetail.toolPlan.length > 0 ? fromDetail.toolPlan : fromResult.toolPlan,
    successCriteria:
      (fromDetail.successCriteria?.length ?? 0) > 0
        ? fromDetail.successCriteria
        : fromResult.successCriteria,
    userVisiblePlan:
      fromDetail.userVisiblePlan.length > 0
        ? fromDetail.userVisiblePlan
        : fromResult.userVisiblePlan,
    planHistory:
      (fromDetail.planHistory?.length ?? 0) > 0 ? fromDetail.planHistory : fromResult.planHistory,
    replanEvents:
      fromDetail.replanEvents.length > 0 ? fromDetail.replanEvents : fromResult.replanEvents,
    requiresConfirmation: fromDetail.requiresConfirmation ?? fromResult.requiresConfirmation,
    reasoningSummary: fromDetail.reasoningSummary ?? fromResult.reasoningSummary,
  };

  const hasData =
    merged.constraints.length > 0 ||
    merged.toolPlan.length > 0 ||
    (merged.successCriteria?.length ?? 0) > 0 ||
    merged.userVisiblePlan.length > 0 ||
    (merged.planHistory?.length ?? 0) > 0 ||
    merged.replanEvents.length > 0 ||
    merged.requiresConfirmation != null ||
    Boolean(merged.reasoningSummary);

  return hasData ? merged : null;
}

export function getToolPlanStep(
  detail: WorkflowDetail | null,
  toolKey: string,
): PlannerToolStep | undefined {
  return resolveAgenticPlannerData(detail)?.toolPlan.find((step) => step.tool === toolKey);
}

export function formatConstraintLabel(constraint: PlannerConstraint): string {
  const label = constraint.label ?? constraint.key.replace(/_/g, " ");
  return `${label}: ${constraint.value}`;
}

export function formatReplanEvent(event: ReplanEvent): string {
  const actionLabel = REPLAN_ACTION_LABELS[event.action] ?? event.action.replace(/_/g, " ");
  const toolDetail = event.inserted_tools?.length
    ? ` — added ${event.inserted_tools.join(", ")}`
    : event.skipped_tools?.length
      ? ` — skipped ${event.skipped_tools.join(", ")}`
      : event.trigger_tool
        ? ` — after ${event.trigger_tool}`
        : "";
  return `${actionLabel}${toolDetail}: ${event.reason}`;
}

export function resolvePlannedAgentsFromToolPlan(detail: WorkflowDetail | null): string[] {
  const toolPlan = resolveAgenticPlannerData(detail)?.toolPlan ?? [];
  if (toolPlan.length === 0) return [];

  const agents = toolPlan
    .filter((step) => !step.skipped && PIPELINE_TOOL_KEYS.includes(step.tool as PipelineToolKey))
    .map((step) => step.tool);

  return agents.length > 0 ? ["planner", ...agents] : [];
}

export function hasAgenticPlannerData(detail: WorkflowDetail | null): boolean {
  return resolveAgenticPlannerData(detail) != null;
}

export const PIPELINE_AGENT_NAMES = ["planner", "job_search", "job_evaluation"] as const;

export const SEARCH_RERUN_PIPELINE_AGENTS = [
  "job_search",
  "company_research",
  "job_evaluation",
] as const;

export const WORKFLOW_INTENTS = [
  "job_discovery",
  "tailor_resume",
  "cover_letter",
  "interview_prep",
  "application_tracking",
] as const;

export function isJobDiscoveryIntent(intent: WorkflowIntent | string | undefined): boolean {
  return !intent || intent === "job_discovery";
}

export function resolveWorkflowIntent(detail: WorkflowDetail | null): WorkflowIntent {
  if (detail?.workflow_intent) {
    return detail.workflow_intent as WorkflowIntent;
  }
  const fromContext = detail?.workflow.context?.workflow_intent;
  if (typeof fromContext === "string" && WORKFLOW_INTENTS.includes(fromContext as WorkflowIntent)) {
    return fromContext as WorkflowIntent;
  }
  const fromResult = detail?.workflow.result?.workflow_intent;
  if (typeof fromResult === "string" && WORKFLOW_INTENTS.includes(fromResult as WorkflowIntent)) {
    return fromResult as WorkflowIntent;
  }
  return "job_discovery";
}

export function resolveIntentClassification(
  detail: WorkflowDetail | null,
): IntentClassification | null {
  const raw = detail?.workflow.result?.intent_classification;
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (typeof record.intent !== "string") return null;
  return {
    intent: record.intent,
    method: typeof record.method === "string" ? record.method : "rule_based",
    matched_phrase:
      typeof record.matched_phrase === "string" ? record.matched_phrase : null,
    planned_agents: Array.isArray(record.planned_agents)
      ? record.planned_agents.filter((item): item is string => typeof item === "string")
      : undefined,
    goal_excerpt:
      typeof record.goal_excerpt === "string" ? record.goal_excerpt : undefined,
  };
}

export const WORKFLOW_INTENT_LABELS: Record<WorkflowIntent, string> = {
  job_discovery: "Job discovery",
  tailor_resume: "Resume tailoring",
  cover_letter: "Cover letter",
  interview_prep: "Interview prep",
  application_tracking: "Applications",
};

export function formatInterviewPrepTargetSource(
  source: WorkflowDetail["interview_prep_target_source"],
): string | undefined {
  switch (source) {
    case "application":
      return "Target: your active application pipeline.";
    case "opportunity":
      return "Target: a saved or high-match opportunity.";
    case "general":
      return "Target: your resume and goal (not tied to one application).";
    default:
      return undefined;
  }
}

export function interviewPrepNextAction(detail: WorkflowDetail | null): string | undefined {
  if (!detail?.next_action) return undefined;
  const targetHint = formatInterviewPrepTargetSource(detail.interview_prep_target_source);
  if (!targetHint) return detail.next_action;
  return `${detail.next_action} ${targetHint}`;
}

export function jobDiscoveryCompletionMessage(detail: WorkflowDetail): string {
  const { accepted_count, evaluated_count, discovered_count } = detail;

  if (accepted_count > 0) {
    if (discovered_count > 0) {
      return `Found ${accepted_count} high-match role${accepted_count === 1 ? "" : "s"}`;
    }
    return `Re-evaluated ${evaluated_count} backlog role${evaluated_count === 1 ? "" : "s"} — ${accepted_count} high match`;
  }
  if (evaluated_count > 0) {
    return `Evaluated ${evaluated_count} role${evaluated_count === 1 ? "" : "s"} — review results below`;
  }
  if (discovered_count > 0) {
    return `Discovered ${discovered_count} role${discovered_count === 1 ? "" : "s"}`;
  }
  return "Workflow finished — explore your results";
}

export function resolvePlannedAgents(detail: WorkflowDetail | null): string[] {
  const fromToolPlan = resolvePlannedAgentsFromToolPlan(detail);
  if (fromToolPlan.length > 0) {
    return fromToolPlan;
  }
  if (detail?.planned_agents?.length) {
    return detail.planned_agents;
  }
  const fromResult = detail?.workflow.result?.planned_agents;
  if (Array.isArray(fromResult) && fromResult.length > 0) {
    return fromResult.filter((item): item is string => typeof item === "string");
  }
  const fromContext = detail?.workflow.context?.planned_agents;
  if (Array.isArray(fromContext) && fromContext.length > 0) {
    return fromContext.filter((item): item is string => typeof item === "string");
  }
  const intent = resolveWorkflowIntent(detail);
  if (intent === "interview_prep") {
    return ["planner", "interview_prep"];
  }
  if (!isJobDiscoveryIntent(intent)) {
    return ["planner"];
  }
  return [...PIPELINE_AGENT_NAMES];
}

export const POLL_INTERVAL_MS = 2500;

export const ON_DEMAND_AGENT_NAMES = [

  "company_research",

  "resume_tailor",

  "cover_letter",

  "interview_prep",

  "decision",

] as const;



export type PipelineStepState = "pending" | "running" | "completed" | "failed" | "idle";

export interface ReasoningTraceEntry {
  label: string;
  detail: string;
  variant?: "default" | "replan" | "constraint" | "approval" | "skipped";
}

export interface PipelineStepInfo {
  key: string;
  label: string;
  state: PipelineStepState;
  execution?: AgentExecution;
  summary?: string;
  detail?: string;
  toolRationale?: string;
  reasoningTrace?: ReasoningTraceEntry[];
  isActive: boolean;
}



export function isWorkflowActive(status: string): boolean {

  return status === "running" || status === "pending";

}

export function isSearchRerunActive(detail: WorkflowDetail | null): boolean {
  if (!detail) return false;
  if (detail.search_rerun_in_progress) return true;
  const fromResult = detail.workflow.result?.search_rerun_in_progress;
  return fromResult === true;
}

function searchRerunStartedAt(detail: WorkflowDetail | null): string | undefined {
  const fromResult = detail?.workflow.result?.search_rerun_started_at;
  return typeof fromResult === "string" ? fromResult : undefined;
}

export function pipelineExecutionsForDisplay(
  executions: AgentExecution[],
  detail: WorkflowDetail | null,
): AgentExecution[] {
  if (!isSearchRerunActive(detail)) {
    return executions;
  }

  const rerunStartedAt = searchRerunStartedAt(detail);
  if (rerunStartedAt) {
    const filtered = executions.filter((execution) => {
      const timestamp = execution.started_at ?? execution.created_at;
      return timestamp >= rerunStartedAt;
    });
    if (filtered.length > 0) {
      return filtered;
    }
  }

  return executions.filter(
    (execution) =>
      !SEARCH_RERUN_PIPELINE_AGENTS.includes(
        execution.agent_name as (typeof SEARCH_RERUN_PIPELINE_AGENTS)[number],
      ) || execution.status === "running" || execution.status === "pending",
  );
}



export function findAgent(

  executions: AgentExecution[],

  agentName: string,

): AgentExecution | undefined {

  const matches = executions.filter((execution) => execution.agent_name === agentName);

  if (matches.length === 0) return undefined;

  return matches.reduce((latest, execution) => {

    const latestTs = latest.started_at ?? latest.created_at;

    const executionTs = execution.started_at ?? execution.created_at;

    return executionTs > latestTs ? execution : latest;

  });

}



function stepStateFromExecution(

  execution: AgentExecution | undefined,

  waiting: boolean,

): PipelineStepState {

  if (execution?.status === "failed") return "failed";

  if (execution?.status === "running" || execution?.status === "pending") return "running";

  if (execution?.status === "completed") return "completed";

  if (waiting) return "pending";

  return "idle";

}



function outputCount(execution: AgentExecution | undefined, key: string): number | undefined {

  const value = execution?.output_data?.[key];

  return typeof value === "number" ? value : undefined;

}



function evaluationExecutions(executions: AgentExecution[]): AgentExecution[] {

  return executions.filter((execution) => execution.agent_name === "job_evaluation");

}



function evaluationStepState(

  executions: AgentExecution[],

  detail: WorkflowDetail | null,

  jobSearchDone: boolean,

  workflowActive: boolean,

): PipelineStepState {

  if (!jobSearchDone && executions.length === 0) {

    return workflowActive ? "pending" : "idle";

  }



  const anyRunning = executions.some(

    (execution) => execution.status === "running" || execution.status === "pending",

  );

  const anyFailed = executions.some((execution) => execution.status === "failed");

  const completedCount = executions.filter((execution) => execution.status === "completed").length;

  const evaluatedCount = Math.max(detail?.evaluated_count ?? 0, completedCount);



  if (anyRunning) return "running";

  if (isToolProgressRunning(detail, "job_evaluation")) return "running";

  if (!jobSearchDone) {
    if (evaluatedCount > 0 || completedCount > 0) {
      return workflowActive ? "pending" : "idle";
    }
    if (anyFailed) return "failed";
    if (executions.length > 0 && workflowActive) return "running";
    return workflowActive ? "pending" : "idle";
  }

  if (evaluatedCount > 0) return "completed";

  if (anyFailed) return "failed";

  if (executions.length > 0 && workflowActive) return "running";

  if (jobSearchDone && workflowActive) return "pending";

  return "idle";

}



function evaluationSummary(

  detail: WorkflowDetail | null,

  executions: AgentExecution[],

  evalRunning: boolean,

): string | undefined {

  const completedExecutions = executions.filter((execution) => execution.status === "completed");

  const evaluatedCount = Math.max(detail?.evaluated_count ?? 0, completedExecutions.length);



  if (evalRunning) {

    if (evaluatedCount > 0) {

      return `Evaluated ${evaluatedCount} role${evaluatedCount === 1 ? "" : "s"} so far...`;

    }

    return "Scoring discovered roles against your preferences...";

  }



  const latestCompleted = completedExecutions.at(-1);

  if (latestCompleted?.reasoning_summary) {

    return latestCompleted.reasoning_summary;

  }



  if (evaluatedCount > 0) {

    const parts = [`Evaluated ${evaluatedCount} role${evaluatedCount === 1 ? "" : "s"}`];

    if ((detail?.accepted_count ?? 0) > 0) {

      parts.push(`${detail?.accepted_count} high match`);

    }

    if ((detail?.top_match_score ?? 0) > 0) {

      parts.push(`top score ${detail?.top_match_score}/100`);

    }

    return `${parts.join(" — ")}.`;

  }



  return undefined;

}



function jobSearchSummary(

  detail: WorkflowDetail | null,

  jobSearch: AgentExecution | undefined,

): string | undefined {

  if (jobSearch?.reasoning_summary) return jobSearch.reasoning_summary;

  if (detail?.job_search_summary) return detail.job_search_summary;



  const discovered =

    outputCount(jobSearch, "discovered_count") ?? detail?.discovered_count ?? 0;

  if (discovered > 0) {

    return `Discovered ${discovered} role${discovered === 1 ? "" : "s"} so far.`;

  }



  return undefined;

}



function guidedNextStepLabel(intent: WorkflowIntent): string {
  switch (intent) {
    case "tailor_resume":
      return "Next: pick an opportunity to tailor";
    case "cover_letter":
      return "Next: pick an opportunity for cover letter";
    case "interview_prep":
      return "Interview prep";
    case "application_tracking":
      return "Next: review your application pipeline";
    default:
      return "Next steps";
  }
}

function guidedNextStepDetail(
  intent: WorkflowIntent,
  detail: WorkflowDetail | null,
): string | undefined {
  if (detail?.next_action) return detail.next_action;

  const saved = detail?.saved_count ?? 0;
  const highMatch = detail?.high_match_count ?? 0;
  const existing = detail?.existing_opportunity_count ?? 0;

  if (intent === "tailor_resume" || intent === "cover_letter") {
    if (saved > 0 || highMatch > 0) {
      return `${saved + highMatch} saved or high-match opportunit${saved + highMatch === 1 ? "y" : "ies"} ready.`;
    }
    if (existing > 0) {
      return `${existing} opportunit${existing === 1 ? "y" : "ies"} available — pick one to continue.`;
    }
    return "Save or discover opportunities first, then run tailoring on demand.";
  }

  if (intent === "interview_prep") {
    return "Interview prep runs automatically after planning when possible.";
  }

  if (intent === "application_tracking") {
    return "Update statuses and follow-ups on the Applications Kanban board.";
  }

  return undefined;
}

function appendToolPlanRationale(
  entries: ReasoningTraceEntry[],
  detail: WorkflowDetail | null,
  toolKey: string,
): void {
  const toolStep = getToolPlanStep(detail, toolKey);
  if (!toolStep?.why) return;
  entries.push({
    label: "Why this tool",
    detail: toolStep.why,
  });
  if (toolStep.requires_confirmation) {
    entries.push({
      label: "Approval required",
      detail: "This step waits for your confirmation before running.",
      variant: "approval",
    });
  }
  if (toolStep.skipped && toolStep.skip_reason) {
    entries.push({
      label: "Skipped",
      detail: toolStep.skip_reason,
      variant: "skipped",
    });
  }
}

function buildAgenticPlannerTraceEntries(
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const plannerData = resolveAgenticPlannerData(detail);
  if (!plannerData) return [];

  const entries: ReasoningTraceEntry[] = [];

  plannerData.constraints.forEach((constraint) => {
    entries.push({
      label: "Constraint",
      detail: formatConstraintLabel(constraint),
      variant: "constraint",
    });
  });

  plannerData.toolPlan.forEach((step) => {
    const toolLabel = AGENT_LABELS[step.tool] ?? step.tool.replace(/_/g, " ");
    if (step.skipped) {
      entries.push({
        label: `Skipped: ${toolLabel}`,
        detail: step.skip_reason ?? step.why ?? "Not needed for this goal.",
        variant: "skipped",
      });
      return;
    }
    if (step.why) {
      entries.push({
        label: toolLabel,
        detail: step.why,
      });
    }
    if (step.requires_confirmation) {
      entries.push({
        label: `${toolLabel} approval`,
        detail: "Requires your confirmation before running.",
        variant: "approval",
      });
    }
  });

  plannerData.successCriteria?.forEach((criterion) => {
    const metLabel =
      criterion.met == null ? "" : criterion.met ? " (met)" : " (pending)";
    entries.push({
      label: "Success criterion",
      detail: `${criterion.description}${metLabel}`,
    });
  });

  plannerData.userVisiblePlan.forEach((step, index) => {
    entries.push({
      label: step.title || `Plan step ${index + 1}`,
      detail: step.description ?? step.title,
    });
  });

  plannerData.replanEvents.forEach((event) => {
    entries.push({
      label: "Replan",
      detail: formatReplanEvent(event),
      variant: "replan",
    });
  });

  if (plannerData.requiresConfirmation) {
    entries.push({
      label: "User approval",
      detail: "One or more steps need your confirmation before they run.",
      variant: "approval",
    });
  }

  if (plannerData.reasoningSummary) {
    entries.push({
      label: "Planner summary",
      detail: plannerData.reasoningSummary,
    });
  }

  return entries;
}

function plannerReasoningTrace(
  execution: AgentExecution | undefined,
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const agenticEntries = buildAgenticPlannerTraceEntries(detail);
  if (agenticEntries.length > 0) {
    return agenticEntries;
  }

  const entries: ReasoningTraceEntry[] = [];
  const intent = resolveWorkflowIntent(detail);
  entries.push({
    label: "Workflow intent",
    detail: WORKFLOW_INTENT_LABELS[intent],
  });
  const classification = resolveIntentClassification(detail);
  if (classification?.matched_phrase) {
    entries.push({
      label: "Matched phrase",
      detail: `"${classification.matched_phrase}" in your goal`,
    });
  }

  const context = (execution?.input_data?.context ?? detail?.workflow.context) as
    | Record<string, unknown>
    | undefined;
  const preferences = context?.preferences as Record<string, unknown> | undefined;
  const targetRoles = preferences?.target_roles;
  if (Array.isArray(targetRoles) && targetRoles.length > 0) {
    entries.push({
      label: "Target roles",
      detail: targetRoles
        .filter((role): role is string => typeof role === "string")
        .slice(0, 3)
        .join(", "),
    });
  }
  const targetLocations = preferences?.target_locations;
  if (Array.isArray(targetLocations) && targetLocations.length > 0) {
    entries.push({
      label: "Locations",
      detail: targetLocations
        .filter((location): location is string => typeof location === "string")
        .slice(0, 3)
        .join(", "),
    });
  }

  const activeResume = context?.active_resume as Record<string, unknown> | undefined;
  if (typeof activeResume?.filename === "string" && activeResume.filename) {
    const healthScore = activeResume.health_score;
    entries.push({
      label: "Resume",
      detail:
        typeof healthScore === "number"
          ? `${activeResume.filename} (health ${healthScore})`
          : activeResume.filename,
    });
  }

  const memorySnippets = context?.memory_snippets;
  if (Array.isArray(memorySnippets) && memorySnippets.length > 0) {
    entries.push({
      label: "Memory context",
      detail: `${memorySnippets.length} snippet(s) from your career history`,
    });
  }

  const pipelineCounts = context?.pipeline_counts as Record<string, unknown> | undefined;
  if (pipelineCounts) {
    const pipelineParts: string[] = [];
    for (const [key, label] of [
      ["applications", "application"],
      ["materials", "material"],
      ["interview_plans", "interview plan"],
    ] as const) {
      const count = pipelineCounts[key];
      if (typeof count === "number" && count > 0) {
        pipelineParts.push(`${count} ${label}${count === 1 ? "" : "s"}`);
      }
    }
    if (pipelineParts.length > 0) {
      entries.push({
        label: "Existing pipeline",
        detail: pipelineParts.join(", "),
      });
    }
  }

  const plannedAgents =
    (Array.isArray(execution?.output_data?.planned_agents)
      ? (execution?.output_data?.planned_agents as string[])
      : undefined) ?? resolvePlannedAgents(detail);
  if (plannedAgents.length > 0) {
    entries.push({
      label: "Agents to run",
      detail: plannedAgents
        .map((agent) => AGENT_LABELS[agent as keyof typeof AGENT_LABELS] ?? agent)
        .join(" → "),
    });
  }

  const suggestedSteps = detail?.suggested_steps?.length
    ? detail.suggested_steps
    : Array.isArray(execution?.output_data?.suggested_steps)
      ? (execution?.output_data?.suggested_steps as Array<
          | string
          | { title?: string; description?: string }
        >)
      : [];
  suggestedSteps.slice(0, 4).forEach((step, index) => {
    if (typeof step === "string") {
      entries.push({ label: `Step ${index + 1}`, detail: step });
      return;
    }
    const title = step.title ?? `Step ${index + 1}`;
    const description = step.description?.trim();
    entries.push({
      label: `Step ${index + 1}`,
      detail: description ? `${title} — ${description}` : title,
    });
  });

  const reasoning = execution?.reasoning_summary?.trim();
  if (reasoning && reasoning !== detail?.plan_summary?.trim()) {
    entries.push({ label: "Rationale", detail: reasoning });
  }

  return entries;
}

function jobSearchReasoningTrace(
  execution: AgentExecution | undefined,
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const entries: ReasoningTraceEntry[] = [];
  appendToolPlanRationale(entries, detail, "job_search");
  const discovered =
    outputCount(execution, "discovered_count") ?? detail?.discovered_count ?? 0;
  if (discovered > 0) {
    entries.push({
      label: "Discovery",
      detail: `${discovered} role${discovered === 1 ? "" : "s"} found across configured providers`,
    });
  }
  const providers = detail?.provider_summary?.providers ?? {};
  const providerNames = Object.keys(providers);
  if (providerNames.length > 0) {
    entries.push({
      label: "Providers",
      detail: providerNames
        .map((name) => {
          const entry = providers[name];
          const count = entry.count ?? 0;
          return `${name}: ${count} (${entry.status ?? "unknown"})`;
        })
        .join("; "),
    });
  }
  if (execution?.reasoning_summary) {
    entries.push({ label: "Search summary", detail: execution.reasoning_summary });
  }
  return entries;
}

function formatRecommendation(recommendation: string | undefined): string {
  if (!recommendation) return "";
  return recommendation.replace(/_/g, " ");
}

export function formatToolProgressEvent(event: WorkflowToolProgressEvent): string {
  if (event.kind === "job_evaluation") {
    const title = event.job_title ?? "Role";
    const company = event.company ? ` at ${event.company}` : "";
    const score =
      typeof event.match_score === "number" ? ` — ${event.match_score}% fit` : "";
    const recommendation = formatRecommendation(event.recommendation);
    const suffix = recommendation ? ` (${recommendation})` : "";
    return `Evaluated ${title}${company}${score}${suffix}`;
  }

  const company = event.company ?? "Company";
  if (event.available === false) {
    return `Research unavailable for ${company}`;
  }
  const summary = event.summary?.trim();
  if (summary) {
    return `Researched ${company}: ${summary}`;
  }
  return `Researched ${company}`;
}

export function resolveActiveToolProgress(
  detail: WorkflowDetail | null,
): WorkflowToolProgress | null {
  const progress = detail?.tool_progress;
  if (!progress || progress.status !== "running") {
    return null;
  }
  return progress;
}

function isToolProgressRunning(
  detail: WorkflowDetail | null,
  tool: WorkflowToolProgress["tool"],
): boolean {
  const progress = detail?.tool_progress;
  return progress?.tool === tool && progress.status === "running";
}

function appendToolProgressEntries(
  entries: ReasoningTraceEntry[],
  detail: WorkflowDetail | null,
  tool: WorkflowToolProgress["tool"],
): void {
  const progress = detail?.tool_progress;
  if (!progress || progress.tool !== tool) {
    return;
  }

  if (progress.status === "running" && progress.current_label) {
    entries.push({
      label: "In progress",
      detail: progress.current_label,
    });
  }

  if (progress.total > 0) {
    entries.push({
      label: "Progress",
      detail: `${progress.current}/${progress.total}`,
    });
  }

  for (const event of progress.recent_events ?? []) {
    entries.push({
      label: event.kind === "job_evaluation" ? "Evaluated" : "Researched",
      detail: formatToolProgressEvent(event),
    });
  }
}

function companyResearchReasoningTrace(
  execution: AgentExecution | undefined,
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const entries: ReasoningTraceEntry[] = [];
  appendToolPlanRationale(entries, detail, "company_research");
  appendToolProgressEntries(entries, detail, "company_research");
  const companyCount = outputCount(execution, "company_count") ?? outputCount(execution, "researched_count");
  if (typeof companyCount === "number" && companyCount > 0) {
    entries.push({
      label: "Companies researched",
      detail: `${companyCount} compan${companyCount === 1 ? "y" : "ies"}`,
    });
  }
  if (execution?.reasoning_summary) {
    entries.push({ label: "Research summary", detail: execution.reasoning_summary });
  }
  return entries;
}

function evaluationReasoningTrace(
  executions: AgentExecution[],
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const entries: ReasoningTraceEntry[] = [];
  appendToolPlanRationale(entries, detail, "job_evaluation");
  appendToolProgressEntries(entries, detail, "job_evaluation");
  const evaluated = detail?.evaluated_count ?? 0;
  const accepted = detail?.accepted_count ?? 0;
  const topScore = detail?.top_match_score ?? 0;
  if (evaluated > 0) {
    entries.push({
      label: "Evaluated",
      detail: `${evaluated} role${evaluated === 1 ? "" : "s"}`,
    });
  }
  if (accepted > 0) {
    entries.push({
      label: "High match",
      detail: `${accepted} role${accepted === 1 ? "" : "s"} at or above threshold`,
    });
  }
  if (topScore > 0) {
    entries.push({ label: "Top score", detail: `${topScore}/100` });
  }
  const latest = executions.filter((item) => item.status === "completed").at(-1);
  const jobTitle = latest?.input_data?.job_title;
  if (typeof jobTitle === "string" && jobTitle) {
    entries.push({ label: "Latest role", detail: jobTitle });
  }
  const matchScore = latest?.output_data?.match_score;
  if (typeof matchScore === "number") {
    entries.push({ label: "Latest score", detail: `${matchScore}/100` });
  }
  if (latest?.reasoning_summary) {
    entries.push({ label: "Evaluation note", detail: latest.reasoning_summary });
  }
  return entries;
}

function resumeTailorReasoningTrace(
  execution: AgentExecution | undefined,
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const entries: ReasoningTraceEntry[] = [];
  appendToolPlanRationale(entries, detail, "resume_tailor");
  if (detail?.selected_opportunity_id) {
    entries.push({
      label: "Target role",
      detail: `Opportunity ${detail.selected_opportunity_id}`,
    });
  }
  const materialType = execution?.output_data?.material_type;
  if (typeof materialType === "string") {
    entries.push({ label: "Material", detail: materialType.replace(/_/g, " ") });
  }
  if (execution?.reasoning_summary) {
    entries.push({ label: "Tailoring", detail: execution.reasoning_summary });
  }
  return entries;
}

function interviewPrepReasoningTrace(
  execution: AgentExecution | undefined,
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const entries: ReasoningTraceEntry[] = [];
  appendToolPlanRationale(entries, detail, "interview_prep");
  const target = formatInterviewPrepTargetSource(detail?.interview_prep_target_source);
  if (target) {
    entries.push({ label: "Target", detail: target });
  }
  const sectionCount = execution?.output_data?.section_count;
  if (typeof sectionCount === "number") {
    entries.push({
      label: "Prep sections",
      detail: `${sectionCount} section${sectionCount === 1 ? "" : "s"}`,
    });
  }
  if (execution?.reasoning_summary) {
    entries.push({ label: "Prep summary", detail: execution.reasoning_summary });
  }
  return entries;
}

function guidedNextReasoningTrace(
  intent: WorkflowIntent,
  detail: WorkflowDetail | null,
): ReasoningTraceEntry[] {
  const entries: ReasoningTraceEntry[] = [];
  entries.push({
    label: "Guided flow",
    detail: WORKFLOW_INTENT_LABELS[intent],
  });
  const nextDetail = guidedNextStepDetail(intent, detail);
  if (nextDetail) {
    entries.push({ label: "Recommendation", detail: nextDetail });
  }
  return entries;
}

function toolRationaleForStep(
  detail: WorkflowDetail | null,
  toolKey: string,
): string | undefined {
  return getToolPlanStep(detail, toolKey)?.why;
}

export function buildPipelineSteps(
  detail: WorkflowDetail | null,
  isPolling: boolean,
): PipelineStepInfo[] {
  const executions = pipelineExecutionsForDisplay(
    detail?.agent_executions ?? [],
    detail,
  );
  const workflowStatus = detail?.workflow.status;
  const workflowActive = workflowStatus ? isWorkflowActive(workflowStatus) : isPolling;
  const workflowIntent = resolveWorkflowIntent(detail);
  const plannedAgents = resolvePlannedAgents(detail);
  const jobDiscovery = plannedAgents.includes("job_search");

  const planner = findAgent(executions, "planner");
  const plannerDone = planner?.status === "completed";
  const tailorSelectionPending = Boolean(detail?.tailor_selection_pending);

  const plannerStep: Omit<PipelineStepInfo, "isActive"> = {
    key: "planner",
    label: AGENT_LABELS.planner,
    state: stepStateFromExecution(planner, workflowActive && !planner),
    execution: planner,
    summary:
      resolveAgenticPlannerData(detail)?.reasoningSummary ||
      planner?.reasoning_summary ||
      detail?.plan_summary ||
      undefined,
    toolRationale: toolRationaleForStep(detail, "planner"),
    reasoningTrace: plannerReasoningTrace(planner, detail),
    detail:
      planner?.status === "running" || planner?.status === "pending"
        ? "Building your plan from profile, resume, and memory context..."
        : workflowActive && !planner
          ? "Launching planner with your profile and resume context..."
          : plannerDone
            ? detail?.next_action && !jobDiscovery && !tailorSelectionPending
              ? detail.next_action
              : jobDiscovery
                ? "Searching jobs..."
                : tailorSelectionPending
                  ? "Plan ready — pick a role below."
                  : undefined
            : undefined,
  };

  if (!jobDiscovery) {
    if (workflowIntent === "tailor_resume") {
      const resumeTailor = findAgent(executions, "resume_tailor");
      const tailorPending = detail?.tailor_selection_pending ?? false;
      const materialReady = Boolean(detail?.tailored_material_id);

      const rawSteps: Omit<PipelineStepInfo, "isActive">[] = [plannerStep];

      if (resumeTailor || materialReady) {
        rawSteps.push({
          key: "resume_tailor",
          label: AGENT_LABELS.resume_tailor,
          state: stepStateFromExecution(
            resumeTailor,
            workflowActive && plannerDone && !resumeTailor && !materialReady,
          ),
          execution: resumeTailor,
          summary:
            resumeTailor?.reasoning_summary ||
            (materialReady ? detail?.next_action || "Tailored resume generated." : undefined),
          toolRationale: toolRationaleForStep(detail, "resume_tailor"),
          reasoningTrace: resumeTailorReasoningTrace(resumeTailor, detail),
          detail:
            resumeTailor?.status === "running" || resumeTailor?.status === "pending"
              ? "Tailoring your resume to the selected role..."
              : undefined,
        });
      } else if (tailorPending && plannerDone) {
        rawSteps.push({
          key: "select_role",
          label: "Select role to tailor for",
          state: "pending",
          summary: "Waiting for you to pick a role.",
          reasoningTrace: guidedNextReasoningTrace("tailor_resume", detail),
          detail: "Interactive step — use the panel below.",
        });
      }

      let activeIndex = rawSteps.findIndex((step) => step.state === "running");
      if (activeIndex === -1) {
        activeIndex = rawSteps.findIndex((step) => step.state === "pending");
      }
      return rawSteps.map((step, index) => ({
        ...step,
        isActive: index === activeIndex,
      }));
    }

    if (workflowIntent === "interview_prep") {
      const interviewPrep = findAgent(executions, "interview_prep");
      const planReady = Boolean(detail?.interview_plan_id);

      const rawSteps: Omit<PipelineStepInfo, "isActive">[] = [plannerStep];

      if (interviewPrep || planReady) {
        rawSteps.push({
          key: "interview_prep",
          label: AGENT_LABELS.interview_prep,
          state: stepStateFromExecution(
            interviewPrep,
            workflowActive && plannerDone && !interviewPrep && !planReady,
          ),
          execution: interviewPrep,
          summary:
            interviewPrep?.reasoning_summary ||
            (planReady
              ? interviewPrepNextAction(detail) || "Interview prep plan generated."
              : undefined),
          toolRationale: toolRationaleForStep(detail, "interview_prep"),
          reasoningTrace: interviewPrepReasoningTrace(interviewPrep, detail),
          detail:
            interviewPrep?.status === "running" || interviewPrep?.status === "pending"
              ? "Building your interview prep roadmap and practice questions..."
              : planReady
                ? formatInterviewPrepTargetSource(detail?.interview_prep_target_source)
                : undefined,
        });
      } else if (plannerDone && workflowActive) {
        rawSteps.push({
          key: "interview_prep",
          label: AGENT_LABELS.interview_prep,
          state: "pending",
          summary: "Generating interview prep plan...",
          reasoningTrace: interviewPrepReasoningTrace(undefined, detail),
          detail: "Selecting the best application or building a general prep plan...",
        });
      }

      let activeIndex = rawSteps.findIndex((step) => step.state === "running");
      if (activeIndex === -1) {
        activeIndex = rawSteps.findIndex((step) => step.state === "pending");
      }
      return rawSteps.map((step, index) => ({
        ...step,
        isActive: index === activeIndex,
      }));
    }

    const nextStep: Omit<PipelineStepInfo, "isActive"> = {
      key: "guided_next",
      label: guidedNextStepLabel(workflowIntent),
      state: plannerDone ? "completed" : workflowActive ? "pending" : "idle",
      summary: plannerDone ? detail?.next_action || guidedNextStepDetail(workflowIntent, detail) : undefined,
      reasoningTrace: guidedNextReasoningTrace(workflowIntent, detail),
      detail: plannerDone
        ? guidedNextStepDetail(workflowIntent, detail)
        : workflowActive && !plannerDone
          ? "Waiting for planner to finish..."
          : undefined,
    };

    const rawSteps = [plannerStep, nextStep];
    let activeIndex = rawSteps.findIndex((step) => step.state === "running");
    if (activeIndex === -1) {
      activeIndex = rawSteps.findIndex((step) => step.state === "pending");
    }
    return rawSteps.map((step, index) => ({
      ...step,
      isActive: index === activeIndex,
    }));
  }

  const jobSearch = findAgent(executions, "job_search");
  const evaluationRuns = evaluationExecutions(executions);
  const evaluationRunning = evaluationRuns.some(
    (execution) => execution.status === "running" || execution.status === "pending",
  );

  const jobSearchDone = jobSearch?.status === "completed";
  const discoveredCount = Math.max(
    detail?.discovered_count ?? 0,
    outputCount(jobSearch, "discovered_count") ?? 0,
  );

  const rawSteps: Omit<PipelineStepInfo, "isActive">[] = [plannerStep];

  if (plannedAgents.includes("job_search")) {
    rawSteps.push({
      key: "job_search",
      label: AGENT_LABELS.job_search,
      state: !plannerDone && !jobSearch
        ? workflowActive
          ? "pending"
          : "idle"
        : stepStateFromExecution(jobSearch, workflowActive && plannerDone && !jobSearch),
      execution: jobSearch,
      summary: jobSearchSummary(detail, jobSearch),
      toolRationale: toolRationaleForStep(detail, "job_search"),
      reasoningTrace: jobSearchReasoningTrace(jobSearch, detail),
      detail:
        jobSearch?.status === "running" || jobSearch?.status === "pending"
          ? discoveredCount > 0
            ? `Searching job boards — ${discoveredCount} role${discoveredCount === 1 ? "" : "s"} discovered so far...`
            : "Searching job boards for matching roles..."
          : workflowActive && plannerDone && !jobSearch
            ? "Job search starts after the planner finishes..."
            : undefined,
    });
  }

  if (plannedAgents.includes("company_research")) {
    const companyResearch = findAgent(executions, "company_research");
    const jobSearchDoneOrSkipped = jobSearchDone || !plannedAgents.includes("job_search");
    rawSteps.push({
      key: "company_research",
      label: AGENT_LABELS.company_research,
      state: isToolProgressRunning(detail, "company_research")
        ? "running"
        : !plannerDone && !companyResearch
        ? workflowActive
          ? "pending"
          : "idle"
        : stepStateFromExecution(
            companyResearch,
            workflowActive && plannerDone && jobSearchDoneOrSkipped && !companyResearch,
          ),
      execution: companyResearch,
      summary:
        companyResearch?.reasoning_summary ??
        (isToolProgressRunning(detail, "company_research")
          ? `Researching companies (${detail?.tool_progress?.current ?? 0}/${detail?.tool_progress?.total ?? 0})...`
          : undefined),
      toolRationale: toolRationaleForStep(detail, "company_research"),
      reasoningTrace: companyResearchReasoningTrace(companyResearch, detail),
      detail:
        companyResearch?.status === "running" || companyResearch?.status === "pending"
          ? (() => {
              const progress = detail?.tool_progress;
              if (
                progress?.tool === "company_research" &&
                progress.status === "running"
              ) {
                const label = progress.current_label ?? "company";
                const count =
                  progress.total > 0
                    ? ` (${progress.current}/${progress.total})`
                    : "";
                return `Researching ${label}${count}...`;
              }
              return "Researching companies to verify stage and hiring signals...";
            })()
          : workflowActive && plannerDone && jobSearchDoneOrSkipped && !companyResearch
            ? "Company research runs after job search..."
            : undefined,
    });
  }

  if (plannedAgents.includes("job_evaluation")) {
    rawSteps.push({
      key: "job_evaluation",
      label: AGENT_LABELS.job_evaluation,
      state: evaluationStepState(evaluationRuns, detail, jobSearchDone, workflowActive),
      execution:
        evaluationRuns.find((execution) => execution.status === "running") ??
        evaluationRuns.at(-1),
      summary: evaluationSummary(detail, evaluationRuns, evaluationRunning),
      toolRationale: toolRationaleForStep(detail, "job_evaluation"),
      reasoningTrace: evaluationReasoningTrace(evaluationRuns, detail),
      detail:
        evaluationRunning
          ? (() => {
              const progress = detail?.tool_progress;
              if (
                progress?.tool === "job_evaluation" &&
                progress.status === "running"
              ) {
                const label = progress.current_label ?? "role";
                const count =
                  progress.total > 0
                    ? ` (${progress.current}/${progress.total})`
                    : "";
                const latest = progress.recent_events?.at(-1);
                if (
                  latest?.kind === "job_evaluation" &&
                  typeof latest.match_score === "number"
                ) {
                  return `Evaluating ${label}${count} — latest: ${latest.match_score}% fit`;
                }
                return `Evaluating ${label}${count}...`;
              }
              const active = evaluationRuns.find(
                (execution) => execution.status === "running",
              );
              const jobTitle = active?.input_data?.job_title;
              if (typeof jobTitle === "string" && jobTitle) {
                return `Evaluating ${jobTitle}...`;
              }
              return "Scoring discovered roles against your preferences...";
            })()
          : workflowActive && jobSearchDone && (detail?.evaluated_count ?? 0) === 0
            ? "Evaluation runs after jobs are discovered..."
            : undefined,
    });
  }

  let activeIndex = rawSteps.findIndex((step) => step.state === "running");
  if (activeIndex === -1) {
    activeIndex = rawSteps.findIndex((step) => step.state === "pending");
  }

  return rawSteps.map((step, index) => ({
    ...step,
    isActive: index === activeIndex,
  }));
}



export function getOnDemandExecutions(

  executions: AgentExecution[],

): AgentExecution[] {

  const seen = new Set<string>();

  return executions

    .filter((execution) => ON_DEMAND_AGENT_NAMES.includes(

      execution.agent_name as (typeof ON_DEMAND_AGENT_NAMES)[number],

    ))

    .filter((execution) => {

      if (seen.has(execution.agent_name)) return false;

      seen.add(execution.agent_name);

      return true;

    });

}

export interface WorkflowQuickReply {
  label: string;
  value: string;
}

const ACTION_TRIGGER_PHRASES: Record<string, string> = {
  generate_interview_prep: "Generate interview prep",
  view_interview_prep: "View prep plan",
  list_applications: "List my applications",
  rerun_search: "Rerun job search",
  tailor_resume: "tailor resume",
  cover_letter: "Generate cover letter",
  show_rejected: "Show rejected roles",
  show_borderline: "Show borderline roles",
  research_company: "Research top company",
  generate_decision: "Generate decision recommendation",
  adjust_threshold: "Lower match threshold",
  update_status: "Update application status",
};

const HELP_QUICK_REPLY: WorkflowQuickReply = {
  label: "What can you do?",
  value: "What can you do?",
};

function actionQuickReply(action: WorkflowActionCard): WorkflowQuickReply {
  return {
    label: action.label,
    value: ACTION_TRIGGER_PHRASES[action.key] ?? action.label,
  };
}

function dedupeQuickReplies(replies: WorkflowQuickReply[], max = 4): WorkflowQuickReply[] {
  const seen = new Set<string>();
  const result: WorkflowQuickReply[] = [];
  for (const reply of replies) {
    const key = reply.value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(reply);
    if (result.length >= max) break;
  }
  return result;
}

export function deriveQuickRepliesFromActions(
  actions: WorkflowActionCard[],
): WorkflowQuickReply[] {
  const actionable = actions.filter((action) => !isLinkOnlyWorkflowAction(action));
  return dedupeQuickReplies(actionable.map(actionQuickReply));
}

export function buildFallbackQuickReplies(
  detail: WorkflowDetail | null,
): WorkflowQuickReply[] {
  const intent = resolveWorkflowIntent(detail);
  const replies: WorkflowQuickReply[] = [];

  if (isJobDiscoveryIntent(intent)) {
    const discovered = detail?.discovered_count ?? 0;
    const accepted = detail?.accepted_count ?? 0;

    if (discovered > 0) {
      replies.push({ label: "Rerun search", value: "Rerun job search" });
      if (accepted > 0) {
        replies.push({ label: "Tailor resume", value: "tailor resume" });
        replies.push({ label: "Cover letter", value: "Generate cover letter" });
        replies.push({ label: "Research company", value: "Research top company" });
      }
      replies.push({ label: "Show rejected", value: "Show rejected roles" });
      replies.push({ label: "Interview prep", value: "Generate interview prep" });
    } else {
      replies.push({ label: "Rerun search", value: "Rerun job search" });
      replies.push({ label: "List applications", value: "List my applications" });
      replies.push({ label: "Interview prep", value: "Generate interview prep" });
      replies.push({ label: "Decision", value: "Generate decision recommendation" });
    }
  } else if (intent === "interview_prep") {
    replies.push({ label: "List applications", value: "List my applications" });
    replies.push({ label: "Interview prep", value: "Generate interview prep" });
    if (detail?.interview_plan_id) {
      replies.push({ label: "Tailor resume", value: "tailor resume" });
    }
  } else if (detail?.interview_plan_id) {
    replies.push({ label: "View prep plan", value: "View prep plan" });
    replies.push({ label: "List applications", value: "List my applications" });
    replies.push({ label: "Interview prep", value: "Generate interview prep" });
  } else if (intent === "tailor_resume" || intent === "cover_letter") {
    if ((detail?.accepted_count ?? 0) > 0 || (detail?.saved_count ?? 0) > 0) {
      replies.push({ label: "Tailor resume", value: "tailor resume" });
      replies.push({ label: "Cover letter", value: "Generate cover letter" });
    }
    replies.push({ label: "List applications", value: "List my applications" });
    replies.push({ label: "Interview prep", value: "Generate interview prep" });
  } else if (intent === "application_tracking") {
    replies.push({ label: "List applications", value: "List my applications" });
    replies.push({ label: "Interview prep", value: "Generate interview prep" });
    replies.push({ label: "Decision", value: "Generate decision recommendation" });
  } else {
    replies.push({ label: "List applications", value: "List my applications" });
    replies.push({ label: "Interview prep", value: "Generate interview prep" });
  }

  const contextual = dedupeQuickReplies(
    replies.filter((reply) => reply.value !== HELP_QUICK_REPLY.value),
    3,
  );
  return [...contextual, HELP_QUICK_REPLY];
}

export function deriveWorkflowQuickReplies(
  messages: WorkflowMessage[],
  detail: WorkflowDetail | null,
): WorkflowQuickReply[] {
  const latestAssistant = [...messages]
    .reverse()
    .find((message) => message.role === "assistant");

  if (latestAssistant?.actions?.length) {
    return deriveQuickRepliesFromActions(latestAssistant.actions);
  }

  return buildFallbackQuickReplies(detail);
}

export function suggestedNextStepLabels(detail: WorkflowDetail): string[] {
  return buildFallbackQuickReplies(detail)
    .filter((reply) => reply.label !== HELP_QUICK_REPLY.label)
    .map((reply) => reply.label);
}

export function workflowRefinementFlags(detail: WorkflowDetail | null) {
  const refinement = detail?.workflow?.context?.refinement;
  if (!refinement || typeof refinement !== "object") {
    return { includeRejected: false, includeBorderline: false };
  }
  const flags = refinement as Record<string, unknown>;
  return {
    includeRejected: flags.include_rejected === true,
    includeBorderline: flags.include_borderline === true,
  };
}

export function parseWorkflowRefinementResult(
  metadata: WorkflowMessage["metadata"] | undefined,
) {
  const result = metadata?.refinement_result;
  if (!result || typeof result !== "object") {
    return null;
  }
  const typed = result as WorkflowRefinementResultMetadata;
  if (!Array.isArray(typed.opportunities) || typed.opportunities.length === 0) {
    return null;
  }
  if (typed.kind !== "rejected" && typed.kind !== "borderline") {
    return null;
  }
  return typed;
}

export interface WorkflowTailorSelectionMetadata {
  pending: boolean;
  tailor_options?: WorkflowDetail["tailor_options"];
}

export function parseTailorSelectionMetadata(
  metadata: WorkflowMessage["metadata"] | undefined,
): WorkflowTailorSelectionMetadata | null {
  const raw = metadata?.tailor_selection;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const record = raw as Record<string, unknown>;
  if (record.pending !== true) {
    return null;
  }
  return {
    pending: true,
    tailor_options:
      record.tailor_options as WorkflowDetail["tailor_options"] | undefined,
  };
}

export function shouldShowTailorSelectorInChat(
  detail: WorkflowDetail | null,
  tailorMetadata: WorkflowTailorSelectionMetadata | null,
): boolean {
  if (!tailorMetadata?.pending) return false;
  if (detail?.tailored_material_id) return false;
  if (detail && isSearchRerunActive(detail)) return false;
  return true;
}

export function findLatestTailorSelectionMessageId(
  messages: WorkflowMessage[],
): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant") continue;
    if (parseTailorSelectionMetadata(message.metadata)?.pending) {
      return message.id;
    }
  }
  return null;
}

export function resolveActiveTailorSelection(
  messages: WorkflowMessage[],
  detail: WorkflowDetail | null,
): WorkflowTailorSelectionMetadata | null {
  const messageId = findLatestTailorSelectionMessageId(messages);
  if (!messageId) return null;
  const message = messages.find((entry) => entry.id === messageId);
  if (!message) return null;
  const tailorSelection = parseTailorSelectionMetadata(message.metadata);
  if (!shouldShowTailorSelectorInChat(detail, tailorSelection)) return null;
  return tailorSelection;
}

export function resolveActiveTailoredMaterialId(
  detail: WorkflowDetail | null,
): string | null {
  if (!detail?.tailored_material_id) return null;
  if (isSearchRerunActive(detail)) return null;
  return detail.tailored_material_id;
}

export function resolveActiveCoverLetterMaterialId(
  detail: WorkflowDetail | null,
): string | null {
  if (!detail?.cover_letter_material_id) return null;
  if (isSearchRerunActive(detail)) return null;
  return detail.cover_letter_material_id;
}

export function shouldRenderMaterialActionInFooter(
  action: WorkflowActionCard,
  detail: WorkflowDetail | null,
): boolean {
  if (
    action.key !== "view_tailored_resume" &&
    action.key !== "download_tailored_resume" &&
    action.key !== "view_cover_letter" &&
    action.key !== "download_cover_letter"
  ) {
    return true;
  }
  if (
    (action.key === "view_tailored_resume" || action.key === "download_tailored_resume") &&
    resolveActiveTailoredMaterialId(detail)
  ) {
    return false;
  }
  if (
    (action.key === "view_cover_letter" || action.key === "download_cover_letter") &&
    resolveActiveCoverLetterMaterialId(detail)
  ) {
    return false;
  }
  return true;
}

export function isLinkOnlyWorkflowAction(action: WorkflowActionCard): boolean {
  if (action.requires_confirmation) return false;
  return (
    action.key === "view_interview_prep" ||
    action.key === "view_tailored_resume" ||
    action.key === "download_tailored_resume" ||
    action.key === "view_cover_letter" ||
    action.key === "download_cover_letter"
  );
}


