"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";

import {
  formatDurationMs,
  statusTone,
} from "@/components/agents/agent-run-utils";
import { AgentActivityCard } from "@/components/agents/agent-activity-card";
import { Button } from "@/components/ui/button";
import type { AgentExecution, WorkflowTimelineItem } from "@/lib/api";
import { cn } from "@/lib/utils";

function resolveTimelineStatus(
  itemType: string,
  status?: string,
  metadata?: Record<string, unknown>,
): string | undefined {
  if (status) return status;
  const metaStatus = metadata?.status;
  if (typeof metaStatus === "string") return metaStatus;
  if (itemType === "workflow_completed") return "completed";
  if (itemType === "workflow_failed") return "failed";
  if (itemType.includes("completed")) return "completed";
  if (itemType.includes("failed")) return "failed";
  return undefined;
}

function TimelineIcon({
  itemType,
  status,
  metadata,
}: {
  itemType: string;
  status?: string;
  metadata?: Record<string, unknown>;
}) {
  const resolved = resolveTimelineStatus(itemType, status, metadata);

  if (resolved === "failed" || itemType.includes("failed")) {
    return <XCircle className="h-4 w-4 text-destructive" />;
  }
  if (resolved === "completed" || itemType.includes("completed")) {
    return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  }
  if (
    resolved === "running" ||
    resolved === "pending" ||
    itemType.includes("running") ||
    (itemType.endsWith("_started") && !resolved)
  ) {
    return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  }
  if (itemType.endsWith("_started")) {
    return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  }
  return <Clock className="h-4 w-4 text-muted-foreground" />;
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

function TimelineDescription({
  description,
  fullDescription,
  compact,
}: {
  description?: string;
  fullDescription?: string;
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = description?.trim() ?? "";
  const full = (fullDescription ?? preview).trim();
  const truncated = full.length > 200 && preview.length > 0 && full !== preview;
  const showExpand = full.length > 200;

  if (!full) return null;

  return (
    <div className="space-y-1">
      <p className="text-muted-foreground">
        {expanded || !showExpand ? full : `${full.slice(0, 200)}…`}
      </p>
      {showExpand ? (
        <button
          type="button"
          className={cn(
            "text-primary hover:underline",
            compact ? "text-xs" : "text-sm",
          )}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Show less" : "Show full reasoning"}
        </button>
      ) : null}
      {truncated && !expanded ? (
        <p className="text-xs text-muted-foreground/80">Preview truncated in timeline</p>
      ) : null}
    </div>
  );
}

interface WorkflowTimelineProps {
  items: WorkflowTimelineItem[];
  agentRuns?: AgentExecution[];
  onViewRun?: (executionId: string) => void;
  compact?: boolean;
}

export function WorkflowTimeline({
  items,
  agentRuns = [],
  onViewRun,
  compact = false,
}: WorkflowTimelineProps) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No timeline events yet for this workflow.</p>
    );
  }

  const runsById = new Map(agentRuns.map((run) => [run.id, run]));

  return (
    <ol className={cn("space-y-3", compact ? "text-xs" : "text-sm")}>
      {items.map((item) => {
        const fullDescription =
          typeof item.metadata?.full_description === "string"
            ? item.metadata.full_description
            : undefined;
        const matchedRun = item.agent_execution_id
          ? runsById.get(item.agent_execution_id)
          : undefined;
        const showActivityCard =
          matchedRun &&
          expandedRunId === item.agent_execution_id &&
          item.item_type.startsWith("agent_");

        return (
          <li
            key={item.id}
            className="relative rounded-lg border border-border bg-card/60 p-3 pl-4"
          >
            <div className="absolute left-0 top-0 h-full w-1 rounded-l-lg bg-primary/30" />
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <TimelineIcon
                    itemType={item.item_type}
                    status={item.status}
                    metadata={item.metadata}
                  />
                  <p className="font-medium">{item.title}</p>
                </div>
                <TimelineDescription
                  description={item.description}
                  fullDescription={fullDescription}
                  compact={compact}
                />
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatTimestamp(item.timestamp)}</span>
                  <span className="rounded-full border border-border px-2 py-0.5">
                    {item.item_type.replace(/_/g, " ")}
                  </span>
                  {item.agent_label ? <span>{item.agent_label}</span> : null}
                  {item.duration_ms != null ? (
                    <span>{formatDurationMs(item.duration_ms)}</span>
                  ) : null}
                  {item.status ? (
                    <span className={cn("rounded-full border px-2 py-0.5", statusTone(item.status))}>
                      {item.status}
                    </span>
                  ) : null}
                </div>
                {showActivityCard ? (
                  <AgentActivityCard
                    execution={matchedRun}
                    onInspect={onViewRun}
                  />
                ) : null}
              </div>
              <div className="flex shrink-0 flex-col gap-2">
                {item.agent_execution_id && matchedRun ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto px-2 text-xs"
                    onClick={() =>
                      setExpandedRunId((current) =>
                        current === item.agent_execution_id ? null : item.agent_execution_id!,
                      )
                    }
                  >
                    {expandedRunId === item.agent_execution_id ? "Hide run" : "Run details"}
                  </Button>
                ) : null}
                {item.agent_execution_id && onViewRun ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onViewRun(item.agent_execution_id!)}
                  >
                    View run
                  </Button>
                ) : item.agent_execution_id ? (
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/agent-runs?execution_id=${item.agent_execution_id}`}>
                      View run
                    </Link>
                  </Button>
                ) : null}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
