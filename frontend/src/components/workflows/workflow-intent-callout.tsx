"use client";

import { RefreshCw, Route } from "lucide-react";

import { AGENT_LABELS } from "@/components/agents/agent-run-utils";
import type { IntentClassification, WorkflowDetail, WorkflowIntent } from "@/lib/api";
import {
  WORKFLOW_INTENT_LABELS,
  formatConstraintLabel,
  formatReplanEvent,
  resolveAgenticPlannerData,
} from "@/lib/workflow-utils";
import { cn } from "@/lib/utils";

interface WorkflowIntentCalloutProps {
  classification: IntentClassification | null | undefined;
  detail?: WorkflowDetail | null;
  className?: string;
}

export function formatIntentReason(classification: IntentClassification): string {
  const intentLabel =
    WORKFLOW_INTENT_LABELS[classification.intent as WorkflowIntent] ??
    classification.intent.replace(/_/g, " ");
  const phrase = classification.matched_phrase?.trim();
  if (phrase) {
    return `Matched "${phrase}" in your goal → ${intentLabel} workflow.`;
  }
  return `Default routing → ${intentLabel} workflow (no specific keyword matched).`;
}

export function WorkflowIntentCallout({
  classification,
  detail,
  className,
}: WorkflowIntentCalloutProps) {
  if (!classification?.intent) return null;

  const plannerData = resolveAgenticPlannerData(detail ?? null);
  const plannedAgents = classification.planned_agents ?? [];
  const activeToolPlan =
    plannerData && plannerData.toolPlan.length > 0
      ? plannerData.toolPlan.filter((step) => !step.skipped)
      : plannedAgents.map((tool) => ({ tool, why: "" as const }));

  return (
    <div
      className={cn(
        "rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 space-y-2",
        className,
      )}
    >
      <p className="flex items-center gap-1.5 text-xs font-medium text-primary">
        <Route className="h-3.5 w-3.5" />
        Why this workflow
      </p>
      <p className="text-sm text-muted-foreground">
        {plannerData?.userVisiblePlan[0]?.title
          ? plannerData.userVisiblePlan[0].title
          : formatIntentReason(classification)}
      </p>
      {plannerData?.userVisiblePlan[0]?.description ? (
        <p className="text-xs text-muted-foreground">
          {plannerData.userVisiblePlan[0].description}
        </p>
      ) : null}

      {plannerData && plannerData.constraints.length > 0 ? (
        <div className="space-y-1">
          <p className="text-xs font-medium text-foreground">Extracted constraints</p>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {plannerData.constraints.map((constraint) => (
              <li key={`${constraint.key}-${constraint.value}`}>
                {formatConstraintLabel(constraint)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {activeToolPlan.length > 0 ? (
        <div className="space-y-1">
          <p className="text-xs font-medium text-foreground">Selected tools</p>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {activeToolPlan.map((step, index) => (
              <li key={`${step.tool}-${index}`}>
                <span className="font-medium text-foreground/90">
                  {AGENT_LABELS[step.tool] ?? step.tool.replace(/_/g, " ")}
                </span>
                {step.why ? `: ${step.why}` : null}
                {"requires_confirmation" in step && step.requires_confirmation ? (
                  <span className="ml-1 text-violet-700 dark:text-violet-300">
                    (needs approval)
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : plannedAgents.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Planned agents: {plannedAgents.join(" → ")}
        </p>
      ) : null}

      {plannerData?.toolPlan.some((step) => step.skipped) ? (
        <div className="space-y-1">
          <p className="text-xs font-medium text-foreground">Skipped tools</p>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {plannerData.toolPlan
              .filter((step) => step.skipped)
              .map((step, index) => (
                <li key={`skipped-${step.tool}-${index}`} className="line-through">
                  {AGENT_LABELS[step.tool] ?? step.tool.replace(/_/g, " ")}
                  {step.skip_reason ? `: ${step.skip_reason}` : null}
                </li>
              ))}
          </ul>
        </div>
      ) : null}

      {plannerData && plannerData.replanEvents.length > 0 ? (
        <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5">
          <p className="flex items-center gap-1 text-xs font-medium text-amber-800 dark:text-amber-300">
            <RefreshCw className="h-3 w-3" />
            Replanning
          </p>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {plannerData.replanEvents.map((event, index) => (
              <li key={`${event.at}-${event.action}-${index}`}>
                {formatReplanEvent(event)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {plannerData?.requiresConfirmation ? (
        <p className="text-xs text-violet-700 dark:text-violet-300">
          Some steps require your approval before they run.
        </p>
      ) : null}
    </div>
  );
}
