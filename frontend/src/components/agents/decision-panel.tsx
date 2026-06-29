"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Loader2, RefreshCw, Sparkles } from "lucide-react";

import { AgentRunDetailSheet } from "@/components/agents/agent-run-detail-sheet";
import { urgencyTone } from "@/components/agents/agent-run-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ApiError,
  decisionsApi,
  type DecisionRecommendation,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface DecisionPanelProps {
  workflowId?: string | null;
  onGenerated?: (recommendation: DecisionRecommendation) => void;
  className?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function formatEvidenceItem(sectionKey: string, item: unknown): string {
  if (typeof item === "string") return item;
  if (!isRecord(item)) return textValue(item) || "Item available";

  if (sectionKey === "recent_activity") {
    const title = textValue(item.title) || "Activity";
    const description = textValue(item.description);
    return description ? `${title}: ${description}` : title;
  }

  if (sectionKey === "workflow_summaries") {
    const name = textValue(item.name) || "Workflow";
    const status = textValue(item.status);
    const result = isRecord(item.result) ? item.result : {};
    const discovered = textValue(result.discovered_count);
    const evaluated = textValue(result.evaluated_count);
    const topMatch = textValue(result.top_match_score);
    const stats = [
      discovered ? `${discovered} discovered` : "",
      evaluated ? `${evaluated} evaluated` : "",
      topMatch ? `top score ${topMatch}` : "",
    ].filter(Boolean);
    return `${name}${status ? ` (${status})` : ""}${stats.length ? `: ${stats.join(", ")}` : ""}`;
  }

  if (sectionKey === "top_opportunities") {
    const title = textValue(item.title) || "Opportunity";
    const company = textValue(item.company);
    const score = textValue(item.match_score);
    const status = textValue(item.status);
    return `${title}${company ? ` at ${company}` : ""}${score ? ` (${score}/100)` : ""}${status ? ` - ${status}` : ""}`;
  }

  if (sectionKey === "applications") {
    const title = textValue(item.job_title) || "Application";
    const company = textValue(item.job_company);
    const stage = textValue(item.stage);
    return `${title}${company ? ` at ${company}` : ""}${stage ? ` - ${stage}` : ""}`;
  }

  if (sectionKey === "materials") {
    const materialType = textValue(item.material_type) || "Material";
    return `${materialType}${item.opportunity_id ? ` for opportunity ${textValue(item.opportunity_id)}` : ""}`;
  }

  if (sectionKey === "interview_plans") {
    const title = textValue(item.job_title) || "Interview prep";
    return title;
  }

  return Object.entries(item)
    .slice(0, 4)
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${textValue(value) || "available"}`)
    .join("; ");
}

function formatEvidenceValue(sectionKey: string, value: unknown): string[] {
  if (value === null || value === undefined) return ["None"];
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return ["None"];
    return value.slice(0, 5).map((item) => formatEvidenceItem(sectionKey, item));
  }
  if (isRecord(value)) {
    return Object.entries(value)
      .slice(0, 6)
      .map(([key, entryValue]) => `${key.replace(/_/g, " ")}: ${textValue(entryValue) || "available"}`);
  }
  return ["Evidence available"];
}

export function DecisionPanel({ workflowId, onGenerated, className }: DecisionPanelProps) {
  const [recommendation, setRecommendation] = useState<DecisionRecommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailExecutionId, setDetailExecutionId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);

  const loadLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const latest = await decisionsApi.latest();
      setRecommendation(latest);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setRecommendation(null);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to load recommendation");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLatest();
  }, [loadLatest]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await decisionsApi.generate(
        workflowId ? { workflow_id: workflowId } : undefined,
      );
      setRecommendation(result.recommendation);
      onGenerated?.(result.recommendation);
      setExpanded(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate recommendation");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      <Card className={cn("flex min-h-0 flex-col rounded-none border-0 border-t border-primary/20 bg-card/80 shadow-none", className)}>
        <CardHeader className="shrink-0 space-y-0 px-5 pb-2 pt-4">
          <CardTitle className="flex items-center justify-between gap-2 text-base">
            <span className="flex min-w-0 items-center gap-2">
              <Sparkles className="h-4 w-4 shrink-0 text-primary" />
              <span className="truncate">Decision Agent</span>
            </span>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={generating}
                onClick={() => void handleGenerate()}
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : recommendation ? (
                  <>
                    <RefreshCw className="h-4 w-4" />
                    Refresh
                  </>
                ) : (
                  "Generate"
                )}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                aria-expanded={expanded}
                aria-label={expanded ? "Collapse decision panel" : "Expand decision panel"}
                onClick={() => setExpanded((value) => !value)}
              >
                {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
              </Button>
            </div>
          </CardTitle>
        </CardHeader>

        {expanded ? (
          <CardContent className="flex min-h-0 flex-1 flex-col px-5 pb-4 pt-0">
            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-4 pr-3">
                {loading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading latest recommendation...
                  </div>
                ) : null}
                {error ? <p className="text-sm text-destructive">{error}</p> : null}
                {!loading && !recommendation && !error ? (
                  <p className="text-sm text-muted-foreground">
                    Get a prioritized list of next actions across opportunities, applications,
                    materials, and interview prep.
                  </p>
                ) : null}
                {recommendation ? (
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
                                recommendation.prompt_version
                                  ? ` v${recommendation.prompt_version}`
                                  : ""
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
                            <Link href={action.route}>Go to action</Link>
                          </Button>
                        </div>
                      ))}
                    </div>
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
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/agent-runs?decision_id=${recommendation.id}`}>
                          View decision detail
                        </Link>
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            </ScrollArea>
          </CardContent>
        ) : null}
      </Card>

      <AgentRunDetailSheet
        executionId={detailExecutionId}
        onClose={() => setDetailExecutionId(null)}
      />
    </>
  );
}
