"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, Briefcase, Loader2, Search, Sparkles } from "lucide-react";
import Link from "next/link";

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
  type WorkflowStartResult,
} from "@/lib/api";
import { needsOnboarding } from "@/lib/onboarding";

const suggestions = [
  "Find remote senior backend roles at growth-stage startups",
  "Tailor my resume for staff engineer positions in fintech",
  "Research companies hiring for AI platform engineers",
  "Prepare for system design interviews in the next two weeks",
];

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const [goal, setGoal] = useState("");
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [onboardingActive, setOnboardingActive] = useState(false);
  const [workflowResult, setWorkflowResult] = useState<WorkflowStartResult | null>(null);
  const [starting, setStarting] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const plannerStatusRef = useRef<HTMLDivElement>(null);

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
    if (!isAuthenticated) {
      setDashboard(null);
      setOnboardingActive(false);
      setDashboardLoading(false);
      return;
    }
    void loadDashboard();
  }, [isAuthenticated, loadDashboard]);

  useEffect(() => {
    if (!starting && !workflowResult) return;
    plannerStatusRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [starting, workflowResult]);

  const handleOnboardingComplete = (summary: DashboardSummary) => {
    setDashboard(summary);
    setOnboardingActive(needsOnboarding(summary));
  };

  const handleStartWorkflow = async () => {
    const trimmed = goal.trim();
    if (!trimmed) return;

    if (!isAuthenticated) return;

    setStarting(true);
    setWorkflowError(null);
    try {
      const result = await workflowApi.start(trimmed);
      setWorkflowResult(result);
    } catch (err) {
      setWorkflowError(err instanceof ApiError ? err.message : "Failed to start workflow");
      setWorkflowResult(null);
    } finally {
      setStarting(false);
    }
  };

  const showOnboarding =
    isAuthenticated && dashboard && onboardingActive && !dashboardLoading;
  const showGoalWorkspace =
    isAuthenticated && dashboard && !onboardingActive && !dashboardLoading;

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
                      Planner and Job Search agents run synchronously
                    </p>
                    <Button
                      disabled={!goal.trim() || starting}
                      onClick={() => void handleStartWorkflow()}
                    >
                      {starting ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Searching jobs...
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

              <div ref={plannerStatusRef} className="space-y-3">
                {starting ? (
                  <Card className="border-primary/30 bg-primary/5">
                    <CardContent className="flex items-center gap-3 p-4">
                      <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
                      <div>
                        <p className="text-sm font-medium">Running agents</p>
                        <p className="text-sm text-muted-foreground">
                          Planner is building your plan, then Apify searches job boards
                          and Tavily enriches company research...
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                ) : null}

                {workflowResult ? (
                  <div className="space-y-3">
                    <Card className="border-primary/30 bg-primary/5">
                      <CardContent className="space-y-3 p-4">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-medium">Planner status</p>
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                            {workflowResult.planner_execution.status}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {workflowResult.plan_summary}
                        </p>
                        {workflowResult.suggested_steps.length > 0 ? (
                          <ul className="space-y-2">
                            {workflowResult.suggested_steps.map((step) => (
                              <li
                                key={step.key}
                                className="rounded-lg border border-border bg-background/50 px-3 py-2 text-sm"
                              >
                                <p className="font-medium">{step.title}</p>
                                <p className="text-muted-foreground">{step.description}</p>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </CardContent>
                    </Card>

                    <Card className="border-primary/30 bg-primary/5">
                      <CardContent className="space-y-3 p-4">
                        <div className="flex items-center justify-between gap-2">
                          <p className="flex items-center gap-1.5 text-sm font-medium">
                            <Search className="h-4 w-4" />
                            Job Search status
                          </p>
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                            {workflowResult.job_search_execution.status}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {workflowResult.job_search_summary}
                        </p>
                        {workflowResult.provider_summary?.providers?.apify ? (
                          <p className="text-xs text-muted-foreground">
                            Apify:{" "}
                            {workflowResult.provider_summary.providers.apify.count ?? 0}{" "}
                            listings (
                            {workflowResult.provider_summary.providers.apify.status})
                          </p>
                        ) : null}
                        {workflowResult.provider_summary?.providers?.tavily_research ? (
                          <p className="text-xs text-muted-foreground">
                            Tavily:{" "}
                            {workflowResult.provider_summary.providers.tavily_research
                              .companies_enriched ?? 0}{" "}
                            companies enriched
                          </p>
                        ) : null}
                        {workflowResult.discovered_count > 0 ? (
                          <Button asChild size="sm">
                            <Link href="/opportunities">
                              <Briefcase className="h-4 w-4" />
                              View {workflowResult.discovered_count} opportunit
                              {workflowResult.discovered_count === 1 ? "y" : "ies"}
                            </Link>
                          </Button>
                        ) : (
                          <p className="text-xs text-muted-foreground">
                            No jobs found yet. Configure APIFY_API_TOKEN and
                            APIFY_JOB_ACTOR_IDS to enable discovery.
                          </p>
                        )}
                        <Button asChild variant="outline" size="sm">
                          <Link href="/workspace">Open workspace</Link>
                        </Button>
                      </CardContent>
                    </Card>
                  </div>
                ) : null}
              </div>

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
          ) : !isAuthenticated ? (
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
                      Sign in to start a workflow
                    </p>
                    <Button asChild disabled={!goal.trim()}>
                      <Link href="/login">
                        Sign in to start
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
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
            </>
          ) : null}
          </div>
        </div>
      )}
    </AppShell>
  );
}
