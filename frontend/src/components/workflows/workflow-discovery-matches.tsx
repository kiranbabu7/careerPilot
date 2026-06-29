"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Briefcase, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { OpportunityDetailSheet } from "@/components/opportunities/opportunity-detail-sheet";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { opportunitiesApi, type Opportunity } from "@/lib/api";
import { cn } from "@/lib/utils";

interface WorkflowDiscoveryMatchesProps {
  workflowId: string;
  discoveredCount: number;
  evaluatedCount: number;
  acceptedCount: number;
  className?: string;
}

export function WorkflowDiscoveryMatches({
  workflowId,
  discoveredCount,
  evaluatedCount,
  acceptedCount,
  className,
}: WorkflowDiscoveryMatchesProps) {
  const [expanded, setExpanded] = useState(false);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [highMatchThreshold, setHighMatchThreshold] = useState(70);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const hasHighMatches = acceptedCount > 0;
  const canViewRoles = hasHighMatches || evaluatedCount > 0 || discoveredCount > 0;
  const roleFilter = hasHighMatches ? "high_match" : "all";
  const viewCount = hasHighMatches
    ? acceptedCount
    : evaluatedCount > 0
      ? evaluatedCount
      : discoveredCount;
  const opportunitiesHref = `/opportunities?workflow_id=${workflowId}&filter=${roleFilter}`;

  const loadMatches = useCallback(async () => {
    setLoading(true);
    setError(null);
    const filter = acceptedCount > 0 ? "high_match" : "all";
    try {
      const data = await opportunitiesApi.list({
        workflow_id: workflowId,
        filter,
      });
      setHighMatchThreshold(data.high_match_threshold);
      setOpportunities(data.opportunities);
    } catch {
      setError("Failed to load roles.");
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, [workflowId, acceptedCount]);

  useEffect(() => {
    if (!expanded || !canViewRoles) {
      return;
    }
    void loadMatches();
  }, [expanded, canViewRoles, loadMatches]);

  const handleOpportunityUpdated = (updated: Opportunity) => {
    setOpportunities((prev) =>
      prev.map((opportunity) => (opportunity.id === updated.id ? updated : opportunity)),
    );
  };

  if (discoveredCount === 0 && acceptedCount === 0 && evaluatedCount === 0) {
    return null;
  }

  return (
    <>
      <Card className={cn("border-border/60 bg-card/40", className)}>
        <CardContent className="space-y-3 p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-muted-foreground">
              {discoveredCount > 0 ? (
                <span>
                  {discoveredCount} role{discoveredCount === 1 ? "" : "s"} discovered
                </span>
              ) : null}
              {evaluatedCount > 0 ? (
                <span>
                  {discoveredCount > 0 ? " · " : ""}
                  {evaluatedCount} evaluated
                </span>
              ) : null}
              {acceptedCount > 0 ? <span> · {acceptedCount} high match</span> : null}
            </div>

            {canViewRoles ? (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant={expanded ? "secondary" : "default"}
                  onClick={() => setExpanded((open) => !open)}
                >
                  <Briefcase className="h-4 w-4" />
                  {hasHighMatches
                    ? `View ${viewCount} match${viewCount === 1 ? "" : "es"}`
                    : `View ${viewCount} role${viewCount === 1 ? "" : "s"}`}
                  {expanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
                <Button asChild size="sm" variant="outline">
                  <Link href={opportunitiesHref}>Open in Opportunities</Link>
                </Button>
              </div>
            ) : null}
          </div>

          {expanded && canViewRoles ? (
            <div className="space-y-3 border-t border-border/60 pt-3">
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {hasHighMatches ? "Loading high-match roles..." : "Loading evaluated roles..."}
                </div>
              ) : error ? (
                <p className="text-sm text-destructive">{error}</p>
              ) : opportunities.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {hasHighMatches
                    ? "No high-match roles found for this workflow."
                    : "No evaluated roles found for this workflow."}
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {opportunities.map((opportunity) => (
                    <OpportunityCard
                      key={opportunity.id}
                      opportunity={opportunity}
                      highMatchThreshold={highMatchThreshold}
                      onSelect={setSelectedId}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <OpportunityDetailSheet
        opportunityId={selectedId}
        onClose={() => setSelectedId(null)}
        onUpdated={handleOpportunityUpdated}
      />
    </>
  );
}
