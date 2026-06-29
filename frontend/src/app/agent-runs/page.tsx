"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, ExternalLink, Loader2, Search } from "lucide-react";

import { AgentRunDetailSheet } from "@/components/agents/agent-run-detail-sheet";
import {
  AGENT_FILTER_OPTIONS,
  agentLabel,
  formatDuration,
  STATUS_FILTER_OPTIONS,
  statusTone,
} from "@/components/agents/agent-run-utils";
import { WorkflowTimeline } from "@/components/workflows/workflow-timeline";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  agentsApi,
  decisionsApi,
  workflowApi,
  ApiError,
  type AgentExecution,
  type DecisionRecommendation,
  type WorkflowTimelineItem,
} from "@/lib/api";

const PAGE_SIZE = 20;

function AgentRunsPageFallback() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="space-y-6 p-8">
          <div>
            <h1 className="text-2xl font-semibold">Agent Runs</h1>
            <p className="text-sm text-muted-foreground">
              Inspect agent inputs, outputs, reasoning, and workflow timelines.
            </p>
          </div>
          <Card>
            <CardContent className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading agent runs...
            </CardContent>
          </Card>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

function AgentRunsPageContent() {
  const searchParams = useSearchParams();
  const initialWorkflowId = searchParams.get("workflow_id") ?? "";
  const initialExecutionId = searchParams.get("execution_id");
  const initialDecisionId = searchParams.get("decision_id");

  const [executions, setExecutions] = useState<AgentExecution[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [agentName, setAgentName] = useState("");
  const [status, setStatus] = useState("");
  const [workflowId, setWorkflowId] = useState(initialWorkflowId);
  const [search, setSearch] = useState("");

  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(
    initialExecutionId,
  );
  const [timelineItems, setTimelineItems] = useState<WorkflowTimelineItem[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [decisionDetail, setDecisionDetail] = useState<DecisionRecommendation | null>(null);

  const loadExecutions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await agentsApi.listExecutions({
        agent_name: agentName || undefined,
        status: status || undefined,
        workflow_id: workflowId || undefined,
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      });
      setExecutions(data.results);
      setCount(data.count);
    } catch (err) {
      setExecutions([]);
      setCount(0);
      setError(err instanceof ApiError ? err.message : "Failed to load agent runs");
    } finally {
      setLoading(false);
    }
  }, [agentName, offset, search, status, workflowId]);

  const loadTimeline = useCallback(async (id: string) => {
    setTimelineLoading(true);
    try {
      const data = await workflowApi.timeline(id);
      setTimelineItems(data.items);
    } catch {
      setTimelineItems([]);
    } finally {
      setTimelineLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadExecutions();
  }, [loadExecutions]);

  useEffect(() => {
    if (workflowId) {
      void loadTimeline(workflowId);
    } else {
      setTimelineItems([]);
    }
  }, [workflowId, loadTimeline]);

  useEffect(() => {
    if (!initialDecisionId) return;
    void decisionsApi.detail(initialDecisionId).then(setDecisionDetail).catch(() => {
      setDecisionDetail(null);
    });
  }, [initialDecisionId]);

  const pageInfo = useMemo(() => {
    const start = count === 0 ? 0 : offset + 1;
    const end = Math.min(offset + PAGE_SIZE, count);
    return { start, end };
  }, [count, offset]);

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="space-y-6 p-8">
          <div>
            <h1 className="text-2xl font-semibold">Agent Runs</h1>
            <p className="text-sm text-muted-foreground">
              Inspect agent inputs, outputs, reasoning, and workflow timelines.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Filters</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-4">
              <select
                value={agentName}
                onChange={(e) => {
                  setOffset(0);
                  setAgentName(e.target.value);
                }}
                className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">All agents</option>
                {AGENT_FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <select
                value={status}
                onChange={(e) => {
                  setOffset(0);
                  setStatus(e.target.value);
                }}
                className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {STATUS_FILTER_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <Input
                placeholder="Workflow ID"
                value={workflowId}
                onChange={(e) => {
                  setOffset(0);
                  setWorkflowId(e.target.value);
                }}
              />
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="Search reasoning or errors"
                  value={search}
                  onChange={(e) => {
                    setOffset(0);
                    setSearch(e.target.value);
                  }}
                />
              </div>
            </CardContent>
          </Card>

          {decisionDetail ? (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-3">
                <CardTitle className="text-base">Decision detail</CardTitle>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/decisions?selected=${decisionDetail.id}`}>
                    <ExternalLink className="h-4 w-4" />
                    Open in Decisions
                  </Link>
                </Button>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="font-medium">{decisionDetail.summary}</p>
                {decisionDetail.rationale ? (
                  <p className="text-muted-foreground">{decisionDetail.rationale}</p>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {workflowId ? (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-3">
                <CardTitle className="text-base">Workflow timeline</CardTitle>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/workspace?workflow=${workflowId}`}>
                    <ExternalLink className="h-4 w-4" />
                    Open workspace
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                {timelineLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading timeline...
                  </div>
                ) : (
                  <WorkflowTimeline
                    items={timelineItems}
                    onViewRun={setSelectedExecutionId}
                  />
                )}
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Runs</CardTitle>
              <p className="text-xs text-muted-foreground">
                {pageInfo.start}-{pageInfo.end} of {count}
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading runs...
                </div>
              ) : null}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              {!loading && executions.length === 0 ? (
                <p className="text-sm text-muted-foreground">No agent runs match your filters.</p>
              ) : null}
              {executions.map((execution) => (
                <button
                  key={execution.id}
                  type="button"
                  onClick={() => setSelectedExecutionId(execution.id)}
                  className="w-full rounded-lg border border-border bg-card/60 p-4 text-left transition-colors hover:bg-accent/40"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{agentLabel(execution)}</p>
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                        {execution.reasoning_summary || execution.error_message || "No summary"}
                      </p>
                      {execution.workflow_execution ? (
                        <p className="mt-2 text-xs">
                          <span className="text-muted-foreground">Workspace: </span>
                          <Link
                            href={`/workspace?workflow=${execution.workflow_execution}`}
                            className="text-primary underline-offset-4 hover:underline"
                            onClick={(event) => event.stopPropagation()}
                          >
                            {execution.workflow_goal || execution.workflow_name || execution.workflow_execution}
                          </Link>
                        </p>
                      ) : null}
                      <p className="mt-2 text-xs text-muted-foreground">
                        {new Date(execution.created_at).toLocaleString()}
                        {formatDuration(execution) ? ` · ${formatDuration(execution)}` : ""}
                      </p>
                    </div>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusTone(execution.status)}`}
                    >
                      {execution.status}
                    </span>
                  </div>
                </button>
              ))}

              <div className="flex items-center justify-between pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= count}
                  onClick={() => setOffset((value) => value + PAGE_SIZE)}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <AgentRunDetailSheet
          executionId={selectedExecutionId}
          onClose={() => setSelectedExecutionId(null)}
        />
      </AppShell>
    </ProtectedRoute>
  );
}

export default function AgentRunsPage() {
  return (
    <Suspense fallback={<AgentRunsPageFallback />}>
      <AgentRunsPageContent />
    </Suspense>
  );
}
