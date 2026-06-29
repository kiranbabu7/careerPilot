"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { JsonViewer } from "@/components/agents/json-viewer";
import {
  agentLabel,
  formatDuration,
  statusTone,
} from "@/components/agents/agent-run-utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { agentsApi, ApiError, type AgentExecution } from "@/lib/api";

interface AgentRunDetailSheetProps {
  executionId: string | null;
  onClose: () => void;
}

export function AgentRunDetailSheet({ executionId, onClose }: AgentRunDetailSheetProps) {
  const [execution, setExecution] = useState<AgentExecution | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!executionId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await agentsApi.detail(executionId);
      setExecution(detail);
    } catch (err) {
      setExecution(null);
      setError(err instanceof ApiError ? err.message : "Failed to load run detail");
    } finally {
      setLoading(false);
    }
  }, [executionId]);

  useEffect(() => {
    if (executionId) {
      void load();
    } else {
      setExecution(null);
      setError(null);
    }
  }, [executionId, load]);

  if (!executionId) return null;

  const duration = execution ? formatDuration(execution) : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
      <button
        type="button"
        className="flex-1"
        aria-label="Close agent run detail"
        onClick={onClose}
      />
      <aside className="flex h-full w-full max-w-xl flex-col border-l border-border bg-background shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <p className="text-sm text-muted-foreground">Agent run</p>
            <h2 className="text-lg font-semibold">
              {execution ? agentLabel(execution) : "Loading..."}
            </h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading run detail...
            </div>
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {execution ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusTone(execution.status)}`}
                >
                  {execution.status}
                </span>
                {duration ? (
                  <span className="text-xs text-muted-foreground">Duration: {duration}</span>
                ) : null}
              </div>

              {execution.workflow_execution ? (
                <div className="flex flex-col gap-1 text-sm">
                  <span className="text-muted-foreground">Workspace</span>
                  <Link
                    href={`/workspace?workflow=${execution.workflow_execution}`}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {execution.workflow_goal || execution.workflow_name || "Open workspace"}
                  </Link>
                  <Link
                    href={`/agent-runs?workflow_id=${execution.workflow_execution}`}
                    className="text-xs text-muted-foreground underline-offset-4 hover:underline"
                  >
                    View all runs for this workspace
                  </Link>
                </div>
              ) : null}

              {execution.reasoning_summary ? (
                <div>
                  <p className="mb-1 text-sm font-medium">Reasoning</p>
                  <p className="text-sm text-muted-foreground">{execution.reasoning_summary}</p>
                </div>
              ) : null}

              {execution.error_message ? (
                <p className="text-sm text-destructive">{execution.error_message}</p>
              ) : null}

              {(execution.related_entities?.length ?? 0) > 0 ? (
                <div>
                  <p className="mb-2 text-sm font-medium">Related entities</p>
                  <div className="flex flex-wrap gap-2">
                    {execution.related_entities?.map((entity) => (
                      <span
                        key={`${entity.type}-${entity.id}`}
                        className="rounded-md border border-border px-2 py-1 text-xs"
                      >
                        {entity.type}: {entity.label || entity.id}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              <Separator />

              <div>
                <p className="mb-2 text-sm font-medium">Input</p>
                <JsonViewer data={execution.input_data ?? {}} />
              </div>

              <div>
                <p className="mb-2 text-sm font-medium">Output</p>
                <JsonViewer data={execution.output_data ?? {}} />
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
