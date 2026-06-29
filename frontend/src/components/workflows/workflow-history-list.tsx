"use client";

import { Clock, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { WorkflowListItem } from "@/lib/api";
import { WORKFLOW_INTENT_LABELS } from "@/lib/workflow-utils";

function statusTone(status: string): string {
  if (status === "completed") return "text-emerald-700 bg-emerald-50 border-emerald-200";
  if (status === "failed") return "text-destructive bg-destructive/10 border-destructive/20";
  if (status === "running" || status === "pending") {
    return "text-primary bg-primary/10 border-primary/20";
  }
  return "text-muted-foreground bg-muted border-border";
}

function formatWhen(workflow: WorkflowListItem): string {
  const ts = workflow.completed_at ?? workflow.started_at ?? workflow.created_at;
  return new Date(ts).toLocaleString();
}

interface WorkflowHistoryListProps {
  workflows: WorkflowListItem[];
  loading: boolean;
  activeWorkflowId: string | null;
  onSelect: (workflowId: string) => void;
}

export function WorkflowHistoryList({
  workflows,
  loading,
  activeWorkflowId,
  onSelect,
}: WorkflowHistoryListProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading workspace history...
      </div>
    );
  }

  if (workflows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        No past workspaces yet. Start a goal from Home to create your first mission.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {workflows.map((workflow) => {
        const intent = workflow.intent ?? "job_discovery";
        const isActive = workflow.id === activeWorkflowId;

        return (
          <button
            key={workflow.id}
            type="button"
            onClick={() => onSelect(workflow.id)}
            className={cn(
              "w-full rounded-xl border bg-card/60 p-4 text-left transition-colors hover:bg-accent/40",
              isActive && "border-primary/40 ring-1 ring-primary/20",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 font-medium">{workflow.goal}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatWhen(workflow)}
                  </span>
                  <span>
                    {workflow.agent_run_count ?? 0} agent run
                    {(workflow.agent_run_count ?? 0) === 1 ? "" : "s"}
                  </span>
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
                    statusTone(workflow.status),
                  )}
                >
                  {workflow.status}
                </span>
                <span className="rounded-full border border-border bg-muted/50 px-2 py-0.5 text-xs text-muted-foreground">
                  {WORKFLOW_INTENT_LABELS[intent] ?? intent}
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
