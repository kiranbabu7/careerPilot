"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
  Sparkles,
  Target,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { WorkflowMaterialResult } from "@/components/workflows/workflow-material-result";
import {
  ApiError,
  workflowApi,
  type ApplicationMaterial,
  type TailorOpportunityOption,
  type TailorOptions,
  type WorkflowDetail,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface WorkflowTailorSelectorProps {
  workflowId: string;
  detail: WorkflowDetail;
  onWorkflowUpdated: () => Promise<void> | void;
}

function OpportunityOptionCard({
  option,
  disabled,
  loading,
  onSelect,
}: {
  option: TailorOpportunityOption;
  disabled: boolean;
  loading: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(option.id)}
      className={cn(
        "flex w-full items-start gap-3 rounded-lg border border-border/80 bg-card/60 p-4 text-left transition-colors",
        "hover:border-primary/40 hover:bg-card disabled:cursor-not-allowed disabled:opacity-60",
      )}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Building2 className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium leading-tight">{option.title}</p>
        <p className="text-sm text-muted-foreground">{option.company}</p>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {option.match_score != null ? (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 font-medium text-primary">
              {option.match_score}/100 match
            </span>
          ) : null}
          <span className="rounded-full bg-muted px-2 py-0.5 capitalize">{option.status}</span>
          {option.is_remote ? <span>Remote</span> : option.location ? <span>{option.location}</span> : null}
        </div>
      </div>
      {loading ? (
        <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-primary" />
      ) : (
        <Sparkles className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
      )}
    </button>
  );
}

export function WorkflowTailorSelector({
  workflowId,
  detail,
  onWorkflowUpdated,
}: WorkflowTailorSelectorProps) {
  const [options, setOptions] = useState<TailorOptions | null>(detail.tailor_options ?? null);
  const [customOpen, setCustomOpen] = useState(false);
  const [customTitle, setCustomTitle] = useState("");
  const [customCompany, setCustomCompany] = useState("");
  const [customDescription, setCustomDescription] = useState("");
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [material, setMaterial] = useState<ApplicationMaterial | null>(null);

  const selectionPending = detail.tailor_selection_pending ?? false;
  const materialId = detail.tailored_material_id ?? material?.id ?? null;
  const hasMaterial = Boolean(materialId);

  useEffect(() => {
    if (detail.tailor_options) {
      setOptions(detail.tailor_options);
    }
  }, [detail.tailor_options]);

  useEffect(() => {
    if (!selectionPending && !options) {
      void workflowApi
        .tailorOptions(workflowId)
        .then((response) => setOptions(response.tailor_options))
        .catch(() => undefined);
    }
  }, [workflowId, selectionPending, options]);

  const runTailor = useCallback(
    async (payload: { opportunity_id: string } | { title: string; company?: string; job_description: string }) => {
      setError(null);
      setLoadingId("opportunity_id" in payload ? payload.opportunity_id : "custom");
      try {
        const result = await workflowApi.tailorResume(workflowId, payload);
        setMaterial(result.material);
        await onWorkflowUpdated();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to tailor resume.");
      } finally {
        setLoadingId(null);
      }
    },
    [workflowId, onWorkflowUpdated],
  );

  const handleCustomSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!customTitle.trim() || customDescription.trim().length < 20) {
      setError("Provide a title and job description (at least 20 characters).");
      return;
    }
    void runTailor({
      title: customTitle.trim(),
      company: customCompany.trim() || undefined,
      job_description: customDescription.trim(),
    });
  };

  if (hasMaterial && materialId) {
    return <WorkflowMaterialResult materialId={materialId} />;
  }

  if (!selectionPending) {
    return null;
  }

  const opportunityOptions = options?.opportunities ?? [];
  const isBusy = loadingId !== null;

  return (
    <Card className="border-primary/30 bg-card/40">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Target className="h-4 w-4 text-primary" />
          Select role to tailor for
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {detail.next_action ||
            "Choose a matching opportunity or paste a job description to generate your tailored resume."}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {opportunityOptions.length > 0 ? (
          <div className="space-y-2">
            {opportunityOptions.map((option) => (
              <OpportunityOptionCard
                key={option.id}
                option={option}
                disabled={isBusy}
                loading={loadingId === option.id}
                onSelect={(id) => void runTailor({ opportunity_id: id })}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border/80 bg-muted/20 p-4 text-sm text-muted-foreground">
            No saved or evaluated opportunities yet. Paste a job description below, or{" "}
            <Link href="/" className="text-primary underline-offset-4 hover:underline">
              run job discovery
            </Link>{" "}
            first to build a list of roles.
          </div>
        )}

        {options?.supports_custom_jd ? (
          <div className="space-y-3 border-t border-border/60 pt-4">
            <button
              type="button"
              className="flex w-full items-center justify-between text-sm font-medium"
              onClick={() => setCustomOpen((open) => !open)}
            >
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Use custom job description
              </span>
              {customOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>

            {customOpen ? (
              <form onSubmit={handleCustomSubmit} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="tailor-title">Job title</Label>
                    <Input
                      id="tailor-title"
                      value={customTitle}
                      onChange={(event) => setCustomTitle(event.target.value)}
                      placeholder="Staff Engineer"
                      disabled={isBusy}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="tailor-company">Company</Label>
                    <Input
                      id="tailor-company"
                      value={customCompany}
                      onChange={(event) => setCustomCompany(event.target.value)}
                      placeholder="FinCo"
                      disabled={isBusy}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="tailor-description">Job description</Label>
                  <textarea
                    id="tailor-description"
                    value={customDescription}
                    onChange={(event) => setCustomDescription(event.target.value)}
                    placeholder="Paste the full job description here..."
                    rows={6}
                    disabled={isBusy}
                    className="min-h-[140px] w-full resize-y rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </div>
                <Button type="submit" size="sm" disabled={isBusy}>
                  {loadingId === "custom" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Tailoring resume...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Tailor for this role
                    </>
                  )}
                </Button>
              </form>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
