"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";

import { ActivityTimeline } from "@/components/profile/activity-timeline";
import { OnboardingChat } from "@/components/onboarding/onboarding-chat";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import {
  ApiError,
  dashboardApi,
  workflowApi,
  type DashboardSummary,
} from "@/lib/api";
import { needsOnboarding } from "@/lib/onboarding";
import { persistActiveWorkflowId, workspaceUrl } from "@/lib/workflow-session";

const suggestions = [
  "Find remote senior backend roles at growth-stage startups",
  "Tailor my resume for staff engineer positions in fintech",
  "Research companies hiring for AI platform engineers",
  "Prepare for system design interviews in the next two weeks",
];

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [goal, setGoal] = useState("");
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [onboardingActive, setOnboardingActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true);
    try {
      const summary = await dashboardApi.summary();
      setDashboard(summary);
      setOnboardingActive(needsOnboarding(summary));
    } catch {
      setDashboard(null);
      setOnboardingActive(false);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      setDashboard(null);
      setOnboardingActive(false);
      setDashboardLoading(false);
      router.replace("/login");
      return;
    }
    void loadDashboard();
  }, [isAuthenticated, isLoading, loadDashboard, router]);

  const handleOnboardingComplete = (summary: DashboardSummary) => {
    setDashboard(summary);
    setOnboardingActive(false);
  };

  const handleStartWorkflow = async () => {
    const trimmed = goal.trim();
    if (!trimmed) return;

    if (!isAuthenticated) return;

    setSubmitting(true);
    setWorkflowError(null);

    try {
      const { workflow } = await workflowApi.start(trimmed);
      persistActiveWorkflowId(workflow.id);
      router.push(workspaceUrl(workflow.id));
    } catch (err) {
      setWorkflowError(err instanceof ApiError ? err.message : "Failed to start workflow");
      setSubmitting(false);
    }
  };

  const showOnboarding =
    isAuthenticated && dashboard && onboardingActive && !dashboardLoading;
  const showGoalWorkspace =
    isAuthenticated && dashboard && !onboardingActive && !dashboardLoading;

  if (isLoading || !isAuthenticated) {
    return (
      <AppShell>
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading...
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {showOnboarding ? (
        <div className="flex h-full min-h-0 flex-col">
          <OnboardingChat
            dashboard={dashboard}
            onComplete={handleOnboardingComplete}
          />
        </div>
      ) : (
        <div className="flex h-full flex-col items-center px-8 py-12">
          <div className="w-full max-w-3xl space-y-8">
            {isAuthenticated && dashboardLoading ? (
              <Card className="border-primary/20 bg-card/80">
                <CardContent className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading your profile...
                </CardContent>
              </Card>
            ) : null}

            {showGoalWorkspace ? (
            <>
              <div className="space-y-3 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                  What career goal should we work on today?
                </h1>
                <p className="text-muted-foreground">
                  Describe your objective and CareerPilot will plan the next steps with
                  your profile and resume context.
                </p>
              </div>

              <Card className="border-border/80 bg-card/50 backdrop-blur">
                <CardContent className="p-4">
                  <textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="e.g. Help me land a senior full-stack role at a climate tech company in Austin..."
                    className="min-h-[120px] w-full resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <div className="mt-4 flex items-center justify-between gap-4">
                    <p className="text-xs text-muted-foreground">
                      Agents run in Workspace — live pipeline and mission control
                    </p>
                    <Button
                      disabled={!goal.trim() || submitting}
                      onClick={() => void handleStartWorkflow()}
                    >
                      {submitting ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Starting...
                        </>
                      ) : (
                        <>
                          Start planning
                          <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </Button>
                  </div>
                  {workflowError ? (
                    <p className="mt-2 text-sm text-destructive">{workflowError}</p>
                  ) : null}
                </CardContent>
              </Card>

              <div className="space-y-3">
                <p className="text-center text-sm text-muted-foreground">
                  Try one of these goals
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => setGoal(suggestion)}
                      className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-left text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:bg-muted/50 hover:text-foreground"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>

              <Card>
                <CardContent className="p-4">
                  <p className="mb-3 text-sm font-medium">Recent activity</p>
                  <ActivityTimeline events={dashboard.recent_activity} />
                </CardContent>
              </Card>
            </>
          ) : null}
          </div>
        </div>
      )}
    </AppShell>
  );
}
