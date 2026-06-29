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

interface WorkflowRejectedRolesProps {
  workflowId: string;
  rejectedCount: number;
  defaultExpanded?: boolean;
  className?: string;
}

export function WorkflowRejectedRoles({
  workflowId,
  rejectedCount,
  defaultExpanded = false,
  className,
}: WorkflowRejectedRolesProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [highMatchThreshold, setHighMatchThreshold] = useState(70);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const opportunitiesHref = `/opportunities?workflow_id=${workflowId}&filter=rejected`;

  const loadRejected = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await opportunitiesApi.list({
        workflow_id: workflowId,
        filter: "rejected",
      });
      setHighMatchThreshold(data.high_match_threshold);
      setOpportunities(data.opportunities);
    } catch {
      setError("Failed to load rejected roles.");
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    if (defaultExpanded && rejectedCount > 0) {
      setExpanded(true);
    }
  }, [defaultExpanded, rejectedCount]);

  useEffect(() => {
    if (!expanded || rejectedCount === 0) {
      return;
    }
    void loadRejected();
  }, [expanded, rejectedCount, loadRejected]);

  const handleOpportunityUpdated = (updated: Opportunity) => {
    setOpportunities((prev) =>
      prev.map((opportunity) => (opportunity.id === updated.id ? updated : opportunity)),
    );
  };

  if (rejectedCount === 0) {
    return null;
  }

  return (
    <>
      <Card className={cn("border-border/60 bg-card/40", className)}>
        <CardContent className="space-y-3 p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-muted-foreground">
              {rejectedCount} rejected role{rejectedCount === 1 ? "" : "s"} from evaluation
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant={expanded ? "secondary" : "default"}
                onClick={() => setExpanded((open) => !open)}
              >
                <Briefcase className="h-4 w-4" />
                View {rejectedCount} rejected
                {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link href={opportunitiesHref}>Open in Opportunities</Link>
              </Button>
            </div>
          </div>

          {expanded ? (
            <div className="space-y-3 border-t border-border/60 pt-3">
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading rejected roles...
                </div>
              ) : error ? (
                <p className="text-sm text-destructive">{error}</p>
              ) : opportunities.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No rejected roles found for this workflow.
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
