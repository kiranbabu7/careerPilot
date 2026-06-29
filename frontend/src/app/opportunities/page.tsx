"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Briefcase, Loader2, Search } from "lucide-react";
import Link from "next/link";

import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { OpportunityDetailSheet } from "@/components/opportunities/opportunity-detail-sheet";
import { opportunityMatchesCompany } from "@/components/companies/company-utils";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { opportunitiesApi, type LastSearchSummary, type Opportunity } from "@/lib/api";
import { cn } from "@/lib/utils";

type FilterKey = "all" | "saved" | "rejected" | "high_match";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "saved", label: "Saved" },
  { key: "rejected", label: "Rejected" },
  { key: "high_match", label: "High Match" },
];

function OpportunitiesPageFallback() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="p-8">
          <div className="mb-8 space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">Opportunities</h1>
            <p className="text-sm text-muted-foreground">
              Jobs discovered by CareerPilot, evaluated for match score, and enriched
              with company research.
            </p>
          </div>
          <Card className="max-w-lg">
            <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading evaluated opportunities...
            </CardContent>
          </Card>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}

function OpportunitiesPageContent() {
  const searchParams = useSearchParams();
  const workflowIdFromUrl = searchParams.get("workflow_id");
  const filterFromUrl = searchParams.get("filter");
  const companyFromUrl = searchParams.get("company")?.trim() || null;
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [highMatchThreshold, setHighMatchThreshold] = useState(70);
  const [lastSearchSummary, setLastSearchSummary] = useState<LastSearchSummary | null>(
    null,
  );
  const [scopedWorkflowId, setScopedWorkflowId] = useState<string | null>(null);
  const [pendingEvaluationCount, setPendingEvaluationCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>(() => {
    if (filterFromUrl === "high_match") return "high_match";
    if (filterFromUrl === "saved") return "saved";
    if (filterFromUrl === "rejected") return "rejected";
    return "all";
  });
  const [showRejected, setShowRejected] = useState(false);

  useEffect(() => {
    const selected = searchParams.get("selected");
    if (selected) {
      setSelectedId(selected);
    }
  }, [searchParams]);

  useEffect(() => {
    if (filterFromUrl === "high_match") {
      setFilter("high_match");
    } else if (filterFromUrl === "saved") {
      setFilter("saved");
    } else if (filterFromUrl === "rejected") {
      setFilter("rejected");
      setShowRejected(true);
    }
  }, [filterFromUrl]);

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await opportunitiesApi.list({
        workflow_id: workflowIdFromUrl ?? undefined,
        filter:
          workflowIdFromUrl && filterFromUrl === "high_match"
            ? "high_match"
            : workflowIdFromUrl && filterFromUrl === "rejected"
              ? "rejected"
              : workflowIdFromUrl && filterFromUrl === "borderline"
                ? "borderline"
                : workflowIdFromUrl && filterFromUrl === "all"
                  ? "all"
                  : undefined,
        include_rejected: showRejected || filter === "rejected",
        include_low_match: filter === "rejected",
      });
      setHighMatchThreshold(data.high_match_threshold);
      setLastSearchSummary(data.last_search_summary);
      setScopedWorkflowId(data.workflow_execution_id ?? workflowIdFromUrl);
      setPendingEvaluationCount(data.pending_evaluation_count);
      setOpportunities(data.opportunities);
    } catch {
      setError("Failed to load opportunities.");
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, [filter, showRejected, workflowIdFromUrl, filterFromUrl]);

  useEffect(() => {
    void loadOpportunities();
  }, [loadOpportunities]);

  const handleOpportunityUpdated = (updated: Opportunity) => {
    setOpportunities((prev) =>
      prev.map((o) => (o.id === updated.id ? updated : o)),
    );
  };

  const scopedOpportunities = useMemo(() => {
    if (!companyFromUrl) return opportunities;
    return opportunities.filter((opportunity) =>
      opportunityMatchesCompany(opportunity, companyFromUrl),
    );
  }, [opportunities, companyFromUrl]);

  const filtered = useMemo(() => {
    switch (filter) {
      case "saved":
        return scopedOpportunities.filter((o) => o.status === "saved");
      case "rejected":
        return scopedOpportunities.filter((o) => o.status === "rejected");
      case "high_match":
        return scopedOpportunities.filter(
          (o) => (o.match_score ?? 0) >= highMatchThreshold,
        );
      default:
        return scopedOpportunities;
    }
  }, [scopedOpportunities, filter, highMatchThreshold]);

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="p-8">
          <div className="mb-8 space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">Opportunities</h1>
            <p className="text-sm text-muted-foreground">
              {companyFromUrl
                ? `Roles discovered at ${companyFromUrl}.`
                : scopedWorkflowId
                  ? "High-match roles from this workflow discovery run."
                  : "Jobs discovered by CareerPilot, evaluated for match score, and enriched with company research."}
            </p>
            {companyFromUrl ? (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Button asChild variant="outline" size="sm">
                  <Link href="/companies">Back to companies</Link>
                </Button>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/opportunities">Show all opportunities</Link>
                </Button>
              </div>
            ) : scopedWorkflowId ? (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Button asChild variant="outline" size="sm">
                  <Link href={`/workspace?workflow=${scopedWorkflowId}`}>
                    Back to workflow
                  </Link>
                </Button>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/opportunities">Show all opportunities</Link>
                </Button>
              </div>
            ) : null}
          </div>

          {!loading && scopedOpportunities.length > 0 ? (
            <div className="mb-6 flex flex-wrap gap-2">
              {FILTERS.map(({ key, label }) => (
                <Button
                  key={key}
                  size="sm"
                  variant={filter === key ? "default" : "outline"}
                  onClick={() => setFilter(key)}
                  className={cn(filter === key && "pointer-events-none")}
                >
                  {label}
                </Button>
              ))}
            </div>
          ) : null}

          {loading ? (
            <Card className="max-w-lg">
              <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading evaluated opportunities...
              </CardContent>
            </Card>
          ) : error ? (
            <Card className="max-w-lg border-destructive/30">
              <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
            </Card>
          ) : opportunities.length === 0 ? (
            <Card className="max-w-2xl">
              <CardContent className="space-y-4 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
                  {pendingEvaluationCount > 0 ? (
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  ) : (
                    <Search className="h-6 w-6 text-muted-foreground" />
                  )}
                </div>
                <div className="space-y-2">
                  <p className="font-medium">
                    {companyFromUrl
                      ? `No opportunities at ${companyFromUrl}`
                      : pendingEvaluationCount > 0
                        ? "Evaluating discovered roles..."
                        : lastSearchSummary &&
                            lastSearchSummary.evaluated_count > 0 &&
                            lastSearchSummary.accepted_count === 0
                          ? "No high-match opportunities yet"
                          : "No opportunities yet"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {companyFromUrl
                      ? "No evaluated roles match this company in your current opportunity list. Try showing rejected roles or browse all opportunities."
                      : pendingEvaluationCount > 0
                        ? `${pendingEvaluationCount} role${pendingEvaluationCount === 1 ? "" : "s"} awaiting match scoring. Refresh shortly or check workflow status on Home.`
                        : lastSearchSummary &&
                            lastSearchSummary.evaluated_count > 0 &&
                            lastSearchSummary.accepted_count === 0
                          ? `Your latest search found ${lastSearchSummary.discovered_count} job${lastSearchSummary.discovered_count === 1 ? "" : "s"} and evaluated ${lastSearchSummary.evaluated_count}. None met the ${lastSearchSummary.high_match_threshold}% high-match threshold${lastSearchSummary.top_match_score > 0 ? ` (best score: ${lastSearchSummary.top_match_score}%)` : ""}.${lastSearchSummary.borderline_count > 0 ? ` ${lastSearchSummary.borderline_count} borderline match${lastSearchSummary.borderline_count === 1 ? "" : "es"} may appear below.` : lastSearchSummary.rejected_count > 0 ? ` ${lastSearchSummary.rejected_count} were below ${lastSearchSummary.borderline_match_threshold}% and auto-rejected.` : ""} Refine your profile or review rejected roles.`
                          : "Start a career goal from Home to run the Planner and Job Search agents. High-match and borderline roles appear here after automatic evaluation."}
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {companyFromUrl ? (
                    <>
                      <Button asChild variant="outline" size="sm">
                        <Link href="/companies">Back to companies</Link>
                      </Button>
                      <Button asChild variant="ghost" size="sm">
                        <Link href="/opportunities">Show all opportunities</Link>
                      </Button>
                    </>
                  ) : null}
                  {!companyFromUrl && pendingEvaluationCount === 0 ? (
                    <Button asChild variant="outline">
                      <Link href="/">Start a career goal</Link>
                    </Button>
                  ) : null}
                  {!companyFromUrl && lastSearchSummary && lastSearchSummary.rejected_count > 0 ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setShowRejected(true);
                        setFilter("rejected");
                      }}
                    >
                      Show rejected ({lastSearchSummary.rejected_count})
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ) : companyFromUrl && scopedOpportunities.length === 0 ? (
            <Card className="max-w-lg">
              <CardContent className="space-y-4 p-6">
                <p className="text-sm text-muted-foreground">
                  No opportunities at {companyFromUrl} match your current view. Rejected
                  or low-match roles may be hidden.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowRejected(true);
                      setFilter("all");
                    }}
                  >
                    Include rejected
                  </Button>
                  <Button asChild variant="ghost" size="sm">
                    <Link href="/opportunities">Show all opportunities</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : filtered.length === 0 ? (
            <Card className="max-w-lg">
              <CardContent className="p-6 text-sm text-muted-foreground">
                {companyFromUrl
                  ? `No opportunities match this filter at ${companyFromUrl}.`
                  : "No opportunities match this filter."}
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {filtered.map((opportunity) => (
                <OpportunityCard
                  key={opportunity.id}
                  opportunity={opportunity}
                  highMatchThreshold={highMatchThreshold}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          )}

          {!loading && scopedOpportunities.length > 0 ? (
            <p className="mt-6 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Briefcase className="h-3.5 w-3.5" />
                Showing {filtered.length} of {scopedOpportunities.length} opportunit
                {scopedOpportunities.length === 1 ? "y" : "ies"}
                {companyFromUrl ? ` at ${companyFromUrl}` : ""}
              </span>
              {!showRejected && filter !== "rejected" ? (
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-xs"
                  onClick={() => setShowRejected(true)}
                >
                  Include rejected
                </Button>
              ) : null}
            </p>
          ) : null}
        </div>

        <OpportunityDetailSheet
          opportunityId={selectedId}
          onClose={() => setSelectedId(null)}
          onUpdated={handleOpportunityUpdated}
        />
      </AppShell>
    </ProtectedRoute>
  );
}

export default function OpportunitiesPage() {
  return (
    <Suspense fallback={<OpportunitiesPageFallback />}>
      <OpportunitiesPageContent />
    </Suspense>
  );
}
