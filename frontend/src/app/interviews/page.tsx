"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Loader2, MessageSquare, Plus } from "lucide-react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { InterviewFormPanel } from "@/components/interviews/interview-form-panel";
import { InterviewPlanCard } from "@/components/interviews/interview-plan-card";
import { InterviewPlanDetail } from "@/components/interviews/interview-plan-detail";
import { InterviewScheduledCard } from "@/components/interviews/interview-scheduled-card";
import { InterviewScheduledDetail } from "@/components/interviews/interview-scheduled-detail";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  interviewsApi,
  type InterviewPlanSummary,
  type ScheduledInterviewSummary,
} from "@/lib/api";

type SelectedItem =
  | { id: string; type: "scheduled" }
  | { id: string; type: "prep_plan" }
  | null;

function PlanSection({
  title,
  plans,
  onSelect,
}: {
  title: string;
  plans: InterviewPlanSummary[];
  onSelect: (id: string) => void;
}) {
  if (plans.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {plans.map((plan) => (
          <InterviewPlanCard key={plan.id} plan={plan} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}

function UpcomingInterviewsSection({
  interviews,
  onSelect,
}: {
  interviews: ScheduledInterviewSummary[];
  onSelect: (id: string) => void;
}) {
  if (interviews.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Upcoming interviews</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {interviews.map((interview) => (
          <InterviewScheduledCard
            key={interview.id}
            interview={interview}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}

function InterviewsPageFallback() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex flex-col gap-8 p-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Interviews</h1>
            <p className="text-sm text-muted-foreground">
              Track external interviews and review AI prep plans.
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading interviews...
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

function InterviewsPageContent() {
  const searchParams = useSearchParams();
  const [upcomingInterviews, setUpcomingInterviews] = useState<ScheduledInterviewSummary[]>(
    [],
  );
  const [active, setActive] = useState<InterviewPlanSummary[]>([]);
  const [upcomingPrep, setUpcomingPrep] = useState<InterviewPlanSummary[]>([]);
  const [recent, setRecent] = useState<InterviewPlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelectedItem>(null);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    const selectedId = searchParams.get("selected");
    const selectedType = searchParams.get("type");
    if (selectedId) {
      setSelected({
        id: selectedId,
        type: selectedType === "scheduled" ? "scheduled" : "prep_plan",
      });
    }
  }, [searchParams]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await interviewsApi.list();
      setUpcomingInterviews(data.upcoming_interviews);
      setActive(data.active);
      setUpcomingPrep(data.upcoming);
      setRecent(data.recent);
    } catch {
      setError("Failed to load interviews.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const total =
    upcomingInterviews.length + active.length + upcomingPrep.length + recent.length;

  const handleSelectScheduled = (id: string) => {
    setSelected({ id, type: "scheduled" });
  };

  const handleSelectPrep = (id: string) => {
    setSelected({ id, type: "prep_plan" });
  };

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex flex-col gap-8 p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Interviews</h1>
              <p className="text-sm text-muted-foreground">
                Track external interviews and review AI prep plans for your applications.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => setFormOpen(true)}>
                <Plus className="h-4 w-4" />
                Add interview
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/applications">
                  <MessageSquare className="h-4 w-4" />
                  Applications
                </Link>
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading interviews...
            </div>
          ) : error ? (
            <Card>
              <CardContent className="flex items-center justify-between p-6">
                <p className="text-sm text-destructive">{error}</p>
                <Button size="sm" variant="outline" onClick={() => void loadData()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ) : total === 0 ? (
            <Card className="max-w-xl">
              <CardContent className="space-y-3 p-6 text-sm text-muted-foreground">
                <p>No interviews tracked yet.</p>
                <p>
                  Add an external interview manually, or generate prep from an opportunity
                  or application in your pipeline.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => setFormOpen(true)}>
                    Add interview
                  </Button>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/opportunities">Browse opportunities</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-8">
              <UpcomingInterviewsSection
                interviews={upcomingInterviews}
                onSelect={handleSelectScheduled}
              />
              <PlanSection
                title="Active application prep"
                plans={active}
                onSelect={handleSelectPrep}
              />
              <PlanSection
                title="Recent prep plans"
                plans={[...upcomingPrep, ...recent]}
                onSelect={handleSelectPrep}
              />
            </div>
          )}
        </div>

        <InterviewFormPanel
          open={formOpen}
          onClose={() => setFormOpen(false)}
          onCreated={() => void loadData()}
        />

        <InterviewScheduledDetail
          interviewId={selected?.type === "scheduled" ? selected.id : null}
          onClose={() => setSelected(null)}
          onUpdated={() => void loadData()}
          onPrepGenerated={(planId) => {
            void loadData();
            setSelected({ id: planId, type: "prep_plan" });
          }}
        />

        <InterviewPlanDetail
          planId={selected?.type === "prep_plan" ? selected.id : null}
          onClose={() => setSelected(null)}
        />
      </AppShell>
    </ProtectedRoute>
  );
}

export default function InterviewsPage() {
  return (
    <Suspense fallback={<InterviewsPageFallback />}>
      <InterviewsPageContent />
    </Suspense>
  );
}
