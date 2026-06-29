"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Building2, Loader2, RefreshCw, X } from "lucide-react";

import { PrepSectionRenderer } from "@/components/interviews/prep-section-renderer";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  applicationsApi,
  ApiError,
  opportunitiesApi,
  type InterviewPlan,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface InterviewPlanDetailProps {
  planId: string | null;
  onClose: () => void;
}

export function InterviewPlanDetail({ planId, onClose }: InterviewPlanDetailProps) {
  const [plan, setPlan] = useState<InterviewPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryLoading, setRetryLoading] = useState(false);
  const open = planId !== null;

  const loadPlan = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const { interviewsApi } = await import("@/lib/api");
      const data = await interviewsApi.detail(id);
      if (data.type !== "prep_plan") {
        setError("This item is a scheduled interview, not a prep plan.");
        setPlan(null);
        return;
      }
      setPlan(data);
    } catch {
      setError("Failed to load interview plan.");
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!planId) {
      setPlan(null);
      setError(null);
      return;
    }
    void loadPlan(planId);
  }, [planId, loadPlan]);

  const handleRetry = async () => {
    if (!plan) return;
    setRetryLoading(true);
    try {
      if (plan.application_id) {
        const result = await applicationsApi.generateInterviewPrep(plan.application_id);
        setPlan(result.interview_plan);
      } else {
        const result = await opportunitiesApi.generateInterviewPrep(plan.opportunity_id);
        setPlan(result.interview_plan);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to regenerate plan.");
    } finally {
      setRetryLoading(false);
    }
  };

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-border bg-background shadow-xl transition-transform",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <p className="text-sm font-medium text-muted-foreground">Interview prep</p>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading plan...
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : plan ? (
            <div className="space-y-6">
              <div className="space-y-2">
                <h2 className="text-xl font-semibold">{plan.job_title}</h2>
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Building2 className="h-4 w-4" />
                  {plan.job_company}
                </p>
                {plan.reasoning_summary ? (
                  <p className="text-sm text-muted-foreground">{plan.reasoning_summary}</p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/opportunities?selected=${plan.opportunity_id}`}>
                      Opportunity
                    </Link>
                  </Button>
                  {plan.application_id ? (
                    <Button asChild size="sm" variant="outline">
                      <Link href="/applications">Application</Link>
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={retryLoading}
                    onClick={() => void handleRetry()}
                  >
                    {retryLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    Regenerate
                  </Button>
                </div>
              </div>
              <Separator />
              <PrepSectionRenderer content={plan.content} />
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}
