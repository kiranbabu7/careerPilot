"use client";

import Link from "next/link";
import { CheckCircle2, Clock, ExternalLink, Loader2, XCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AGENT_LABELS,
  formatDuration,
} from "@/components/agents/agent-run-utils";
import type { AgentExecution } from "@/lib/api";

function StatusIcon({ status }: { status: string }) {
  if (status === "running") {
    return <Loader2 className="h-3.5 w-3.5 animate-spin" />;
  }
  if (status === "completed") {
    return <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />;
  }
  if (status === "failed") {
    return <XCircle className="h-3.5 w-3.5 text-destructive" />;
  }
  return <Clock className="h-3.5 w-3.5" />;
}

interface AgentActivityCardProps {
  execution: AgentExecution;
  onInspect?: (executionId: string) => void;
}

export function AgentActivityCard({ execution, onInspect }: AgentActivityCardProps) {
  const label = AGENT_LABELS[execution.agent_name] ?? execution.agent_name;
  const duration = formatDuration(execution);
  const output = (execution.output_data ?? {}) as Record<string, unknown>;
  const providerSummary = output.provider_summary as
    | {
        providers?: Record<
          string,
          { count?: number; status?: string; companies_enriched?: number }
        >;
      }
    | undefined;

  return (
    <Card className="bg-card/80">
      <CardHeader className="p-4 pb-2">
        <CardTitle className="flex items-center justify-between text-sm">
          {label}
          <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground">
            <StatusIcon status={execution.status} />
            {execution.status}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        {execution.reasoning_summary ? (
          <p>{execution.reasoning_summary}</p>
        ) : null}
        {duration ? <p>Duration: {duration}</p> : null}
        {typeof output.discovered_count === "number" ? (
          <p>Opportunities found: {output.discovered_count}</p>
        ) : null}
        {typeof output.match_score === "number" ? (
          <p>Match score: {output.match_score}/100</p>
        ) : null}
        {typeof output.recommendation === "string" ? (
          <p className="capitalize">
            Recommendation: {output.recommendation.replace(/_/g, " ")}
          </p>
        ) : null}
        {typeof output.summary === "string" ? (
          <p>Decision: {output.summary}</p>
        ) : null}
        {Array.isArray(output.actions) ? (
          <p>Next actions: {output.actions.length}</p>
        ) : null}
        {typeof output.available === "boolean" ? (
          <p>
            Research: {output.available ? "available" : "unavailable"}
            {typeof output.reason === "string" && output.reason
              ? ` (${output.reason})`
              : ""}
          </p>
        ) : null}
        {typeof output.material_type === "string" ? (
          <p>
            Material: {output.material_type.replace(/_/g, " ")}
            {typeof output.model_name === "string" ? ` (${output.model_name})` : ""}
          </p>
        ) : null}
        {typeof output.used_fallback === "boolean" && output.used_fallback ? (
          <p>Used local fallback draft</p>
        ) : null}
        {typeof output.section_count === "number" ? (
          <p>Prep sections: {output.section_count}</p>
        ) : null}
        {typeof output.interview_plan_id === "string" ? (
          <p>Interview plan generated</p>
        ) : null}
        {providerSummary?.providers?.apify ? (
          <p>
            Apify: {providerSummary.providers.apify.count ?? 0} listings (
            {providerSummary.providers.apify.status})
          </p>
        ) : null}
        {providerSummary?.providers?.tavily_research &&
        (providerSummary.providers.tavily_research.companies_enriched ?? 0) > 0 ? (
          <p>
            Tavily: {providerSummary.providers.tavily_research.companies_enriched ?? 0}{" "}
            companies enriched
          </p>
        ) : null}
        {execution.error_message ? (
          <p className="text-destructive">{execution.error_message}</p>
        ) : null}
        {onInspect ? (
          <button
            type="button"
            className="inline-flex items-center gap-1 text-primary hover:underline"
            onClick={() => onInspect(execution.id)}
          >
            <ExternalLink className="h-3 w-3" />
            Inspect run
          </button>
        ) : (
          <Link
            href={`/agent-runs?execution_id=${execution.id}`}
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <ExternalLink className="h-3 w-3" />
            Inspect run
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
