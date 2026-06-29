"use client";

import Link from "next/link";
import { useState } from "react";

import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { OpportunityDetailSheet } from "@/components/opportunities/opportunity-detail-sheet";
import { Button } from "@/components/ui/button";
import type { Opportunity, WorkflowRefinementResultMetadata } from "@/lib/api";

interface WorkflowChatOpportunityListProps {
  workflowId: string;
  refinementResult: WorkflowRefinementResultMetadata;
}

export function WorkflowChatOpportunityList({
  workflowId,
  refinementResult,
}: WorkflowChatOpportunityListProps) {
  const { kind, count, opportunities } = refinementResult;
  const filter = kind === "rejected" ? "rejected" : "borderline";
  const label =
    kind === "rejected"
      ? `rejected role${count === 1 ? "" : "s"}`
      : `borderline role${count === 1 ? "" : "s"}`;
  const opportunitiesHref = `/opportunities?workflow_id=${workflowId}&filter=${filter}`;

  if (!opportunities.length) {
    return null;
  }

  return (
    <WorkflowChatOpportunityGrid
      opportunities={opportunities}
      label={label}
      opportunitiesHref={opportunitiesHref}
    />
  );
}

interface WorkflowChatOpportunityGridProps {
  opportunities: Opportunity[];
  label: string;
  opportunitiesHref: string;
  highMatchThreshold?: number;
}

export function WorkflowChatOpportunityGrid({
  opportunities,
  label,
  opportunitiesHref,
  highMatchThreshold = 70,
}: WorkflowChatOpportunityGridProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [items, setItems] = useState(opportunities);

  const handleOpportunityUpdated = (updated: Opportunity) => {
    setItems((prev) =>
      prev.map((opportunity) => (opportunity.id === updated.id ? updated : opportunity)),
    );
  };

  return (
    <>
      <div className="mt-2 space-y-3 rounded-lg border border-border/60 bg-card/40 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-medium text-muted-foreground">
            {items.length} {label}
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href={opportunitiesHref}>Open in Opportunities</Link>
          </Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((opportunity) => (
            <OpportunityCard
              key={opportunity.id}
              opportunity={opportunity}
              highMatchThreshold={highMatchThreshold}
              onSelect={setSelectedId}
            />
          ))}
        </div>
      </div>

      <OpportunityDetailSheet
        opportunityId={selectedId}
        onClose={() => setSelectedId(null)}
        onUpdated={handleOpportunityUpdated}
      />
    </>
  );
}
