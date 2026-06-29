"use client";

import Link from "next/link";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import type { OpportunityEvaluation } from "@/lib/api";
import { cn } from "@/lib/utils";

const FACTOR_LABELS: Record<string, string> = {
  role_match: "Role match",
  skill_overlap: "Skill overlap",
  location_fit: "Location fit",
  salary_fit: "Salary fit",
  company_research: "Company research",
};

const FACTOR_ORDER = [
  "role_match",
  "skill_overlap",
  "location_fit",
  "salary_fit",
  "company_research",
];

function scoreTone(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-red-400";
}

export function topFactorSummary(evaluation: OpportunityEvaluation): string | null {
  const factors = evaluation.factors ?? {};
  const orderedKeys = FACTOR_ORDER.filter((key) => key in factors);
  if (orderedKeys.length === 0) return null;

  const topFactor = orderedKeys.reduce((best, key) => {
    const score = factors[key]?.score ?? 0;
    const bestScore = factors[best]?.score ?? 0;
    return score > bestScore ? key : best;
  }, orderedKeys[0]);
  const top = factors[topFactor];
  if (!top) return null;
  return `${FACTOR_LABELS[topFactor] ?? topFactor} (${top.score}/100)`;
}

interface MatchFactorBreakdownProps {
  evaluation: OpportunityEvaluation;
  compact?: boolean;
  className?: string;
}

export function MatchFactorBreakdown({
  evaluation,
  compact = false,
  className,
}: MatchFactorBreakdownProps) {
  const [expanded, setExpanded] = useState(!compact);
  const factors = evaluation.factors ?? {};
  const orderedKeys = FACTOR_ORDER.filter((key) => key in factors);
  const agentExecutionId =
    typeof evaluation.agent_execution_id === "string"
      ? evaluation.agent_execution_id
      : undefined;

  if (orderedKeys.length === 0) return null;

  if (compact) {
    const summary = topFactorSummary(evaluation);
    if (!summary) return null;
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        Top factor: {summary}
      </p>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Match factor breakdown
        </p>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? (
            <>
              Hide
              <ChevronUp className="h-3 w-3" />
            </>
          ) : (
            <>
              Show breakdown
              <ChevronDown className="h-3 w-3" />
            </>
          )}
        </button>
      </div>

      {expanded ? (
        <ul className="space-y-3">
          {orderedKeys.map((key) => {
            const factor = factors[key];
            if (!factor) return null;
            const weightPct = Math.round(factor.weight * 100);
            return (
              <li key={key} className="space-y-1">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium">{FACTOR_LABELS[key] ?? key}</span>
                  <span className="text-muted-foreground">
                    {factor.score}/100 · {weightPct}% weight
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-all", scoreTone(factor.score))}
                    style={{ width: `${factor.score}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{factor.detail}</p>
              </li>
            );
          })}
        </ul>
      ) : null}

      {agentExecutionId ? (
        <Link
          href={`/agent-runs?execution_id=${agentExecutionId}`}
          className="text-xs text-primary underline-offset-4 hover:underline"
        >
          View evaluation agent run
        </Link>
      ) : null}
    </div>
  );
}
