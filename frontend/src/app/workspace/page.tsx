"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Bot, History, Loader2, Radio, Target } from "lucide-react";

import { AgentRunDetailSheet } from "@/components/agents/agent-run-detail-sheet";
import { WorkflowActivityLog } from "@/components/workflows/workflow-activity-log";
import { WorkflowHistoryList } from "@/components/workflows/workflow-history-list";
import { WorkflowMissionControl } from "@/components/workflows/workflow-mission-control";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useWorkflowPolling } from "@/hooks/use-workflow-polling";
import { ApiError, workflowApi, type WorkflowListItem } from "@/lib/api";
import {
  getStoredActiveWorkflowId,
  persistActiveWorkflowId,
} from "@/lib/workflow-session";
import { isWorkflowActive } from "@/lib/workflow-utils";

type WorkspaceTab = "active" | "history";

function WorkspacePageFallback() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-8 text-sm text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          Loading workspace...
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

function WorkspacePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workflowFromUrl = searchParams.get("workflow");
  const goalFromUrl = searchParams.get("goal");
  const tabFromUrl = searchParams.get("tab");

  const [activeTab, setActiveTab] = useState<WorkspaceTab>(
    tabFromUrl === "history" ? "history" : "active",
  );
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [goalStartError, setGoalStartError] = useState<string | null>(null);
  const [startingFromGoal, setStartingFromGoal] = useState(false);
  const goalStartAttemptedRef = useRef(false);

  const {
    workflowDetail,
    timelineItems,
    initialLoading,
    error: workflowError,
    isPolling,
    refetch: refetchWorkflow,
  } = useWorkflowPolling(activeWorkflowId);

  const openWorkflow = useCallback(
    (workflowId: string) => {
      setActiveWorkflowId(workflowId);
      persistActiveWorkflowId(workflowId);
      setActiveTab("active");
      router.replace(`/workspace?workflow=${workflowId}`);
    },
    [router],
  );

  useEffect(() => {
    if (!goalFromUrl || workflowFromUrl || activeWorkflowId || goalStartAttemptedRef.current) {
      return;
    }

    const trimmedGoal = goalFromUrl.trim();
    if (!trimmedGoal) return;

    goalStartAttemptedRef.current = true;
    setStartingFromGoal(true);
    setGoalStartError(null);

    void workflowApi
      .start(trimmedGoal)
      .then(({ workflow }) => {
        openWorkflow(workflow.id);
      })
      .catch((err) => {
        goalStartAttemptedRef.current = false;
        setGoalStartError(
          err instanceof ApiError ? err.message : "Failed to start workflow from goal.",
        );
      })
      .finally(() => {
        setStartingFromGoal(false);
      });
  }, [goalFromUrl, workflowFromUrl, activeWorkflowId, openWorkflow]);

  useEffect(() => {
    if (goalFromUrl?.trim()) return;

    const id = workflowFromUrl ?? getStoredActiveWorkflowId();
    if (id) {
      setActiveWorkflowId(id);
      persistActiveWorkflowId(id);
      if (!workflowFromUrl) {
        router.replace(`/workspace?workflow=${id}`);
      }
    }
  }, [workflowFromUrl, router]);

  useEffect(() => {
    if (tabFromUrl === "history") {
      setActiveTab("history");
    }
  }, [tabFromUrl]);

  const loadWorkflowHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const data = await workflowApi.list();
      setWorkflowHistory(data);
    } catch {
      setWorkflowHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkflowHistory();
  }, [loadWorkflowHistory]);

  useEffect(() => {
    if (!isPolling && activeWorkflowId) {
      void loadWorkflowHistory();
    }
  }, [isPolling, activeWorkflowId, loadWorkflowHistory]);

  const hasActiveWorkflow = Boolean(activeWorkflowId);
  const workflowStatus = workflowDetail?.workflow.status;
  const showMissionControl =
    hasActiveWorkflow &&
    activeTab === "active" &&
    (initialLoading || workflowDetail || workflowError);

  const workflowAgentRuns = workflowDetail?.agent_executions ?? [];

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:h-full">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
          <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-border bg-gradient-to-b from-background via-background to-muted/10 lg:border-r">
            <div className="border-b border-border px-6 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h1 className="text-lg font-semibold">Workspace</h1>
                  <p className="text-sm text-muted-foreground">
                    Mission control and workspace history for your agent workflows
                  </p>
                </div>
                {isPolling ? (
                  <span className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                    <Radio className="h-3 w-3 animate-pulse" />
                    Agents running
                  </span>
                ) : hasActiveWorkflow && workflowStatus && isWorkflowActive(workflowStatus) ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : null}
              </div>

              <div className="mt-4 flex gap-2">
                <Button
                  type="button"
                  variant={activeTab === "active" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveTab("active")}
                >
                  <Target className="h-4 w-4" />
                  Active Mission
                </Button>
                <Button
                  type="button"
                  variant={activeTab === "history" ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setActiveTab("history");
                    router.replace("/workspace?tab=history");
                  }}
                >
                  <History className="h-4 w-4" />
                  Workspace History
                </Button>
              </div>
            </div>

            {activeTab === "history" ? (
              <ScrollArea className="flex-1 px-6 py-6">
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Past workspaces with goals, status, and agent run counts. Select one to
                    reopen its mission control view.
                  </p>
                  <WorkflowHistoryList
                    workflows={workflowHistory}
                    loading={historyLoading}
                    activeWorkflowId={activeWorkflowId}
                    onSelect={openWorkflow}
                  />
                </div>
              </ScrollArea>
            ) : showMissionControl && activeWorkflowId ? (
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4 md:px-6 md:py-5">
                <WorkflowMissionControl
                  workflowId={activeWorkflowId}
                  detail={workflowDetail}
                  agentRuns={workflowAgentRuns}
                  initialLoading={initialLoading}
                  error={workflowError}
                  isPolling={isPolling}
                  onViewRun={setSelectedExecutionId}
                  onWorkflowUpdated={async () => {
                    await refetchWorkflow();
                  }}
                  className="min-h-0 flex-1"
                />
              </div>
            ) : (
              <ScrollArea className="flex-1 px-6 py-6">
                <div className="flex min-h-[420px] flex-col items-center justify-center text-center">
                  <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-border/60 bg-card/50">
                    {startingFromGoal ? (
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    ) : (
                      <Bot className="h-8 w-8 text-muted-foreground" />
                    )}
                  </div>
                  <p className="text-lg font-medium">
                    {startingFromGoal ? "Starting your mission..." : "Ready for your next mission"}
                  </p>
                  <p className="mt-2 max-w-md text-sm text-muted-foreground">
                    {startingFromGoal
                      ? "Launching a workspace from your recommended action."
                      : "Describe a career goal on Home to launch a workflow. The planner chooses which agents run — job search only when discovery is needed."}
                  </p>
                  {goalStartError ? (
                    <p className="mt-3 max-w-md text-sm text-destructive">{goalStartError}</p>
                  ) : null}
                  <div className="mt-6 flex flex-wrap justify-center gap-3">
                    <Button asChild>
                      <Link href="/">
                        Start from Home
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setActiveTab("history");
                        router.replace("/workspace?tab=history");
                      }}
                    >
                      Browse history
                    </Button>
                  </div>
                </div>
              </ScrollArea>
            )}
          </section>

          <aside className="flex min-h-0 w-full shrink-0 flex-col overflow-hidden border-t border-border bg-muted/10 lg:h-full lg:w-[360px] lg:border-t-0 lg:border-l">
            <WorkflowActivityLog
              workflowId={hasActiveWorkflow ? activeWorkflowId : null}
              timelineItems={timelineItems}
              agentRuns={workflowAgentRuns}
              isPolling={isPolling}
              onViewRun={setSelectedExecutionId}
              className="min-h-0 flex-1"
            />
          </aside>
        </div>
        </div>

        <AgentRunDetailSheet
          executionId={selectedExecutionId}
          onClose={() => setSelectedExecutionId(null)}
        />
      </AppShell>
    </ProtectedRoute>
  );
}

export default function WorkspacePage() {
  return (
    <Suspense fallback={<WorkspacePageFallback />}>
      <WorkspacePageContent />
    </Suspense>
  );
}
