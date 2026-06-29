"use client";

import { Loader2 } from "lucide-react";

import type { WorkflowDetail } from "@/lib/api";
import {
  formatToolProgressEvent,
  resolveActiveToolProgress,
} from "@/lib/workflow-utils";
import { cn } from "@/lib/utils";

interface WorkflowToolProgressFeedProps {
  detail: WorkflowDetail | null;
  className?: string;
}

const TOOL_LABELS = {
  job_evaluation: "Job evaluation",
  company_research: "Company research",
} as const;

export function WorkflowToolProgressFeed({
  detail,
  className,
}: WorkflowToolProgressFeedProps) {
  const progress = resolveActiveToolProgress(detail);
  if (!progress) {
    return null;
  }

  const events = progress.recent_events ?? [];
  const toolLabel = TOOL_LABELS[progress.tool] ?? progress.tool;

  return (
    <div
      className={cn(
        "rounded-lg border border-primary/25 bg-primary/5 px-3 py-2.5",
        className,
      )}
    >
      <div className="flex items-center gap-2 text-xs font-medium text-primary">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>
          {toolLabel}
          {progress.total > 0 ? ` — ${progress.current}/${progress.total}` : ""}
        </span>
      </div>

      {progress.current_label ? (
        <p className="mt-1.5 text-sm text-foreground/90">
          {progress.tool === "job_evaluation" ? "Evaluating" : "Researching"}{" "}
          <span className="font-medium">{progress.current_label}</span>
          ...
        </p>
      ) : null}

      {events.length > 0 ? (
        <ul className="mt-2 max-h-28 space-y-1 overflow-y-auto text-xs text-muted-foreground">
          {[...events].reverse().map((event, index) => (
            <li key={`${event.at ?? index}-${event.company ?? event.job_title ?? index}`}>
              {formatToolProgressEvent(event)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
