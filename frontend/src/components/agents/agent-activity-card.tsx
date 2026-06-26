"use client";

import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AgentExecution } from "@/lib/api";

const AGENT_LABELS: Record<string, string> = {
  planner: "Planner",
  job_search: "Job Search",
};

function formatDuration(execution: AgentExecution): string | null {
  if (!execution.started_at || !execution.completed_at) return null;
  const ms =
    new Date(execution.completed_at).getTime() -
    new Date(execution.started_at).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

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

export function AgentActivityCard({ execution }: { execution: AgentExecution }) {
  const label = AGENT_LABELS[execution.agent_name] ?? execution.agent_name;
  const duration = formatDuration(execution);
  const output = execution.output_data as Record<string, unknown>;
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
        {providerSummary?.providers?.apify ? (
          <p>
            Apify: {providerSummary.providers.apify.count ?? 0} listings (
            {providerSummary.providers.apify.status})
          </p>
        ) : null}
        {providerSummary?.providers?.tavily_research ? (
          <p>
            Tavily: {providerSummary.providers.tavily_research.companies_enriched ?? 0}{" "}
            companies enriched
          </p>
        ) : null}
        {execution.error_message ? (
          <p className="text-destructive">{execution.error_message}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
