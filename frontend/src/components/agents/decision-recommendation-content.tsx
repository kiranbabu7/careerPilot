"use client";

import Link from "next/link";
import { useState } from "react";

import { AgentRunDetailSheet } from "@/components/agents/agent-run-detail-sheet";
import { urgencyTone } from "@/components/agents/agent-run-utils";
import { formatEvidenceValue, resolveDecisionActionRoute } from "@/components/agents/decision-format-utils";
import { Button } from "@/components/ui/button";
import type { DecisionRecommendation } from "@/lib/api";

interface DecisionRecommendationContentProps {
  recommendation: DecisionRecommendation;
}

export function DecisionRecommendationContent({
  recommendation,
}: DecisionRecommendationContentProps) {
  const [detailExecutionId, setDetailExecutionId] = useState<string | null>(null);

  return (
    <>
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium">{recommendation.summary}</p>
          {recommendation.rationale ? (
            <p className="mt-1 text-sm text-muted-foreground">{recommendation.rationale}</p>
          ) : null}
        </div>

        {(recommendation.prompt_name ||
          recommendation.model_name ||
          recommendation.prompt_version) ? (
          <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Model & prompt</p>
            <p className="mt-1">
              {recommendation.model_name}
              {recommendation.prompt_name
                ? ` · ${recommendation.prompt_name}${
                    recommendation.prompt_version ? ` v${recommendation.prompt_version}` : ""
                  }`
                : ""}
            </p>
          </div>
        ) : null}

        {recommendation.input_snapshot &&
        Object.keys(recommendation.input_snapshot).length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Evidence considered
            </p>
            <ul className="space-y-2 text-sm">
              {Object.entries(recommendation.input_snapshot).map(([key, value]) => {
                const lines = formatEvidenceValue(key, value);
                return (
                  <li
                    key={key}
                    className="rounded-lg border border-border/60 bg-background/60 px-3 py-2"
                  >
                    <p className="text-xs font-medium capitalize text-foreground">
                      {key.replace(/_/g, " ")}
                    </p>
                    <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
                      {lines.map((line, index) => (
                        <li key={`${key}-${index}`} className="leading-relaxed">
                          {line}
                        </li>
                      ))}
                    </ul>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}

        {recommendation.actions && recommendation.actions.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Recommended actions
            </p>
            {recommendation.actions.map((action, index) => (
              <div
                key={`${action.title}-${index}`}
                className="rounded-lg border border-border bg-background/60 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{action.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{action.reason}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${urgencyTone(action.urgency)}`}
                  >
                    {action.urgency}
                  </span>
                </div>
                <Button asChild variant="link" size="sm" className="mt-2 h-auto px-0">
                  <Link
                    href={resolveDecisionActionRoute(
                      action,
                      recommendation.workflow_execution,
                    )}
                  >
                    Go to action
                  </Link>
                </Button>
              </div>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {recommendation.agent_execution_id ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDetailExecutionId(recommendation.agent_execution_id)}
            >
              View agent run
            </Button>
          ) : null}
          {recommendation.workflow_execution ? (
            <Button asChild variant="outline" size="sm">
              <Link href={`/workspace?workflow=${recommendation.workflow_execution}`}>
                Open workspace
              </Link>
            </Button>
          ) : null}
        </div>
      </div>

      <AgentRunDetailSheet
        executionId={detailExecutionId}
        onClose={() => setDetailExecutionId(null)}
      />
    </>
  );
}
