"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";

import { WorkflowTimeline } from "@/components/workflows/workflow-timeline";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AgentExecution, WorkflowTimelineItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface WorkflowActivityLogProps {
  workflowId?: string | null;
  timelineItems: WorkflowTimelineItem[];
  agentRuns?: AgentExecution[];
  isPolling?: boolean;
  onViewRun?: (executionId: string) => void;
  className?: string;
}

export function WorkflowActivityLog({
  workflowId,
  timelineItems,
  agentRuns = [],
  isPolling = false,
  onViewRun,
  className,
}: WorkflowActivityLogProps) {
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div className="shrink-0 border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold">Activity log</h2>
            <p className="text-xs text-muted-foreground">
              Timeline of agent and workflow events
            </p>
          </div>
          {workflowId ? (
            <Button asChild variant="link" size="sm" className="h-auto shrink-0 px-0 text-xs">
              <Link href={`/agent-runs?workflow_id=${workflowId}`}>Inspector</Link>
            </Button>
          ) : null}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-5 py-4">
          {!workflowId ? (
            <p className="py-6 text-sm text-muted-foreground">
              Open an active workflow to see its activity timeline.
            </p>
          ) : timelineItems.length > 0 ? (
            <WorkflowTimeline
              items={timelineItems}
              agentRuns={agentRuns}
              onViewRun={onViewRun}
              compact
            />
          ) : isPolling ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Waiting for agent activity...
            </div>
          ) : (
            <p className="py-6 text-sm text-muted-foreground">
              No timeline events yet for this workflow.
            </p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
