"use client";

import {
  Building2,
  ChevronRight,
  MapPin,
  Sparkles,
  Target,
  Wifi,
} from "lucide-react";

import {
  formatMatchScore,
  formatSalary,
  formatSource,
  isBorderlineMatch,
  STATUS_LABELS,
} from "@/components/opportunities/opportunity-utils";
import { MatchFactorBreakdown } from "@/components/opportunities/match-factor-breakdown";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Opportunity, OpportunityEvaluation } from "@/lib/api";
import { cn } from "@/lib/utils";

interface OpportunityCardProps {
  opportunity: Opportunity;
  onSelect: (id: string) => void;
  highMatchThreshold?: number;
}

function statusBadgeClass(status: string): string {
  if (status === "saved") return "bg-green-100 text-green-800";
  if (status === "rejected") return "bg-red-100 text-red-800";
  if (status === "applied") return "bg-blue-100 text-blue-800";
  return "bg-muted text-muted-foreground";
}

export function OpportunityCard({
  opportunity,
  onSelect,
  highMatchThreshold = 70,
}: OpportunityCardProps) {
  const { job } = opportunity;
  const salary = formatSalary(job);
  const matchScore = formatMatchScore(opportunity.match_score);
  const statusLabel = STATUS_LABELS[opportunity.status] ?? opportunity.status;
  const borderline = isBorderlineMatch(opportunity.match_score, highMatchThreshold);
  const evaluation: OpportunityEvaluation | null =
    opportunity.evaluation &&
    typeof opportunity.evaluation === "object" &&
    "factors" in opportunity.evaluation
      ? (opportunity.evaluation as OpportunityEvaluation)
      : null;

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(opportunity.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(opportunity.id);
        }
      }}
      className={cn(
        "flex cursor-pointer flex-col border-border/80 bg-card/80 transition-colors",
        "hover:border-primary/40 hover:bg-card hover:shadow-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <CardHeader className="space-y-2 p-5 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-base font-semibold leading-snug">
              {job.title}
            </CardTitle>
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Building2 className="h-3.5 w-3.5 shrink-0" />
              {job.company}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            {matchScore ? (
              <span
                className={cn(
                  "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
                  borderline
                    ? "bg-amber-100 text-amber-900"
                    : "bg-primary/10 text-primary",
                )}
              >
                <Target className="h-3 w-3" />
                {matchScore}
                {borderline ? (
                  <span className="font-medium opacity-80">borderline</span>
                ) : null}
              </span>
            ) : null}
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                statusBadgeClass(opportunity.status),
              )}
            >
              {statusLabel}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
            {formatSource(job.source)}
          </span>
          {job.location ? (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {job.location}
            </span>
          ) : null}
          {job.is_remote ? (
            <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
              <Wifi className="h-3 w-3" />
              Remote
            </span>
          ) : null}
          {salary ? <span>{salary}</span> : null}
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3 p-5 pt-0">
        {job.description ? (
          <p className="line-clamp-3 text-sm text-muted-foreground">{job.description}</p>
        ) : null}

        {opportunity.match_context ? (
          <div className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
            <p className="mb-0.5 flex items-center gap-1 text-xs font-medium text-primary">
              <Sparkles className="h-3 w-3" />
              Why this match
            </p>
            <p className="line-clamp-2 text-muted-foreground">
              {opportunity.match_context}
            </p>
          </div>
        ) : null}

        {evaluation?.factors && Object.keys(evaluation.factors).length > 0 ? (
          <MatchFactorBreakdown evaluation={evaluation} compact />
        ) : null}

        <p className="mt-auto flex items-center gap-1 pt-2 text-xs font-medium text-primary">
          View details
          <ChevronRight className="h-3.5 w-3.5" />
        </p>
      </CardContent>
    </Card>
  );
}
