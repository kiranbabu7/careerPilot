"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Building2,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  MapPin,
  MessageSquare,
  Send,
  Sparkles,
  Target,
  Wifi,
  X,
} from "lucide-react";

import {
  CompanyResearchDisplay,
  CompanyResearchHeading,
} from "@/components/companies/company-research-display";
import { MatchFactorBreakdown } from "@/components/opportunities/match-factor-breakdown";
import {
  formatMatchScore,
  formatRecommendation,
  formatSalary,
  formatSource,
  hasCompanyResearch,
  materialDisplayContent,
} from "@/components/opportunities/opportunity-utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  applicationsApi,
  opportunitiesApi,
  resumeApi,
  ApiError,
  type Application,
  type ApplicationMaterial,
  type Opportunity,
  type OpportunityEvaluation,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface OpportunityDetailSheetProps {
  opportunityId: string | null;
  onClose: () => void;
  onUpdated?: (opportunity: Opportunity) => void;
}

type ActionKey =
  | "research"
  | "evaluate"
  | "tailor"
  | "cover_letter"
  | "save"
  | "reject"
  | "mark_applied"
  | "interview_prep";

type MaterialTab = "tailored_resume" | "cover_letter";

function materialLabel(type: MaterialTab): string {
  return type === "tailored_resume" ? "Tailored Resume" : "Cover Letter";
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function downloadText(filename: string, content: string) {
  downloadBlob(filename, new Blob([content], { type: "text/markdown;charset=utf-8" }));
}

export function OpportunityDetailSheet({
  opportunityId,
  onClose,
  onUpdated,
}: OpportunityDetailSheetProps) {
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [materials, setMaterials] = useState<ApplicationMaterial[]>([]);
  const [hasActiveResume, setHasActiveResume] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<ActionKey | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [lastAgentExecutionId, setLastAgentExecutionId] = useState<string | null>(null);
  const [materialTab, setMaterialTab] = useState<MaterialTab>("tailored_resume");
  const [copied, setCopied] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [linkedApplication, setLinkedApplication] = useState<Application | null>(null);
  const open = opportunityId !== null;

  const loadMaterials = useCallback(async (id: string) => {
    try {
      const data = await opportunitiesApi.materials(id);
      setMaterials(data.materials);
    } catch {
      setMaterials([]);
    }
  }, []);

  const loadApplication = useCallback(async (id: string) => {
    try {
      const data = await applicationsApi.forOpportunity(id);
      setLinkedApplication(data.application);
    } catch {
      setLinkedApplication(null);
    }
  }, []);

  const loadDetail = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      setOpportunity(null);
      try {
        const [data, resumes] = await Promise.all([
          opportunitiesApi.detail(id),
          resumeApi.list().catch(() => []),
        ]);
        setOpportunity(data);
        setHasActiveResume(resumes.some((resume) => resume.is_active));
        await Promise.all([loadMaterials(id), loadApplication(id)]);
      } catch {
        setError("Failed to load opportunity details.");
      } finally {
        setLoading(false);
      }
    },
    [loadMaterials, loadApplication],
  );

  useEffect(() => {
    if (!opportunityId) {
      setOpportunity(null);
      setMaterials([]);
      setError(null);
      setLoading(false);
      setActionError(null);
      setActionSuccess(null);
      setLastAgentExecutionId(null);
      setHasActiveResume(null);
      setLinkedApplication(null);
      return;
    }
    void loadDetail(opportunityId);
  }, [opportunityId, loadDetail]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  const applyUpdate = (updated: Opportunity, message?: string) => {
    setOpportunity(updated);
    onUpdated?.(updated);
    if (message) {
      setActionSuccess(message);
      setActionError(null);
    }
  };

  const runAction = async (key: ActionKey, fn: () => Promise<void>) => {
    setActionLoading(key);
    setActionError(null);
    setActionSuccess(null);
    setCopied(false);
    try {
      await fn();
    } catch (err) {
      const message =
        err instanceof ApiError && err.message
          ? err.message
          : `Failed to ${key.replace("_", " ")}. Please try again.`;
      setActionError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleResearch = () => {
    if (!opportunity) return;
    void runAction("research", async () => {
      const result = await opportunitiesApi.researchCompany(opportunity.id);
      setLastAgentExecutionId(result.agent_execution.id);
      applyUpdate(result.opportunity, "Company research updated.");
    });
  };

  const handleEvaluate = () => {
    if (!opportunity) return;
    void runAction("evaluate", async () => {
      const result = await opportunitiesApi.evaluate(opportunity.id);
      setLastAgentExecutionId(result.agent_execution.id);
      applyUpdate(result.opportunity, `Match score: ${result.match_score}/100`);
    });
  };

  const handleTailorResume = () => {
    if (!opportunity) return;
    void runAction("tailor", async () => {
      const result = await opportunitiesApi.tailorResume(opportunity.id);
      setLastAgentExecutionId(result.agent_execution.id);
      applyUpdate(result.opportunity, "Tailored resume generated.");
      setMaterials((prev) => [result.material, ...prev]);
      setMaterialTab("tailored_resume");
    });
  };

  const handleCoverLetter = () => {
    if (!opportunity) return;
    void runAction("cover_letter", async () => {
      const result = await opportunitiesApi.generateCoverLetter(opportunity.id);
      setLastAgentExecutionId(result.agent_execution.id);
      applyUpdate(result.opportunity, "Cover letter generated.");
      setMaterials((prev) => [result.material, ...prev]);
      setMaterialTab("cover_letter");
    });
  };

  const handleStatus = (status: "saved" | "rejected") => {
    if (!opportunity) return;
    void runAction(status === "saved" ? "save" : "reject", async () => {
      const updated = await opportunitiesApi.updateStatus(opportunity.id, status);
      applyUpdate(updated, status === "saved" ? "Opportunity saved." : "Opportunity rejected.");
    });
  };

  const handleMarkApplied = () => {
    if (!opportunity) return;
    void runAction("mark_applied", async () => {
      const result = await applicationsApi.createFromOpportunity(opportunity.id);
      setLinkedApplication(result.application);
      const refreshed = await opportunitiesApi.detail(opportunity.id);
      applyUpdate(
        refreshed,
        result.created
          ? "Application created and tracked on the Kanban board."
          : "Application already exists for this opportunity.",
      );
    });
  };

  const handleInterviewPrep = () => {
    if (!opportunity) return;
    void runAction("interview_prep", async () => {
      const result = await opportunitiesApi.generateInterviewPrep(opportunity.id);
      setLastAgentExecutionId(result.agent_execution.id);
      applyUpdate(result.opportunity ?? opportunity, result.reasoning_summary);
    });
  };

  const latestByType = useMemo(() => {
    const map: Partial<Record<MaterialTab, ApplicationMaterial>> = {};
    for (const material of materials) {
      if (!map[material.material_type as MaterialTab]) {
        map[material.material_type as MaterialTab] = material;
      }
    }
    return map;
  }, [materials]);

  const activeMaterial = latestByType[materialTab] ?? null;

  const handleCopy = async () => {
    if (!activeMaterial) return;
    await navigator.clipboard.writeText(materialDisplayContent(activeMaterial));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = async () => {
    if (!activeMaterial || !job) return;
    const slug = job.title.replace(/\s+/g, "-").toLowerCase().slice(0, 40);
    const prefix =
      materialTab === "tailored_resume" ? "tailored-resume" : "cover-letter";

    setDownloadLoading(true);
    try {
      const blob = await resumeApi.downloadMaterialPdf(activeMaterial.id);
      downloadBlob(`${prefix}-${slug}.pdf`, blob);
    } catch {
      downloadText(`${prefix}-${slug}.txt`, materialDisplayContent(activeMaterial));
    } finally {
      setDownloadLoading(false);
    }
  };

  const job = opportunity?.job;
  const salary = job ? formatSalary(job) : null;
  const research = job?.company_research;
  const showResearch = hasCompanyResearch(research);
  const evaluation: OpportunityEvaluation | null =
    opportunity?.evaluation &&
    typeof opportunity.evaluation === "object" &&
    "recommendation" in opportunity.evaluation
      ? (opportunity.evaluation as OpportunityEvaluation)
      : null;
  const matchScoreLabel = formatMatchScore(opportunity?.match_score);
  const materialsReady =
    Boolean(latestByType.tailored_resume) || Boolean(latestByType.cover_letter);

  const showInterviewPrep =
    linkedApplication !== null ||
    opportunity?.status === "saved" ||
    opportunity?.status === "applied" ||
    materialsReady;

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50 transition-opacity duration-200",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden={!open}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Opportunity details"
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-xl transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <p className="text-sm font-medium text-muted-foreground">
            Opportunity details
          </p>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading details...
            </div>
          ) : error ? (
            <div className="space-y-3">
              <p className="text-sm text-destructive">{error}</p>
              {opportunityId ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void loadDetail(opportunityId)}
                >
                  Retry
                </Button>
              ) : null}
            </div>
          ) : job && opportunity ? (
            <div className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <h2 className="text-xl font-semibold leading-snug">
                      {job.title}
                    </h2>
                    <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Building2 className="h-3.5 w-3.5 shrink-0" />
                      {job.company}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                      {formatSource(job.source)}
                    </span>
                    {matchScoreLabel ? (
                      <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
                        {matchScoreLabel}
                      </span>
                    ) : null}
                    {materialsReady ? (
                      <span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-800">
                        Materials ready
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  {job.location ? (
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {job.location}
                    </span>
                  ) : null}
                  {job.is_remote ? (
                    <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                      <Wifi className="h-3 w-3" />
                      Remote
                    </span>
                  ) : null}
                  {salary ? <span>{salary}</span> : null}
                </div>

                {job.apply_url ? (
                  <Button asChild>
                    <a
                      href={job.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Apply
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </Button>
                ) : null}
              </div>

              {evaluation ? (
                <>
                  <Separator />
                  <div className="space-y-3">
                    <p className="flex items-center gap-1.5 text-sm font-medium text-primary">
                      <Target className="h-4 w-4" />
                      Match evaluation
                    </p>
                    <p className="text-sm capitalize text-muted-foreground">
                      {formatRecommendation(evaluation.recommendation)}
                    </p>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {evaluation.rationale}
                    </p>
                    {evaluation.strengths.length > 0 ? (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-green-700">Strengths</p>
                        <ul className="list-inside list-disc text-sm text-muted-foreground">
                          {evaluation.strengths.map((s) => (
                            <li key={s}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {evaluation.gaps.length > 0 ? (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-amber-700">Gaps</p>
                        <ul className="list-inside list-disc text-sm text-muted-foreground">
                          {evaluation.gaps.map((g) => (
                            <li key={g}>{g}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {evaluation.factors && Object.keys(evaluation.factors).length > 0 ? (
                      <MatchFactorBreakdown evaluation={evaluation} />
                    ) : null}
                  </div>
                </>
              ) : null}

              {opportunity.match_context ? (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="flex items-center gap-1.5 text-sm font-medium text-primary">
                      <Sparkles className="h-4 w-4" />
                      Why this match
                    </p>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {opportunity.match_context}
                    </p>
                  </div>
                </>
              ) : null}

              {job.description ? (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Description</p>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                      {job.description}
                    </p>
                  </div>
                </>
              ) : null}

              {showResearch && research ? (
                <>
                  <Separator />
                  <div className="space-y-3">
                    <CompanyResearchHeading />
                    <CompanyResearchDisplay research={research} />
                  </div>
                </>
              ) : null}

              {materialsReady ? (
                <>
                  <Separator />
                  <div className="space-y-3">
                    <p className="flex items-center gap-1.5 text-sm font-medium">
                      <FileText className="h-4 w-4" />
                      Application materials
                    </p>
                    <div className="flex gap-2">
                      {(["tailored_resume", "cover_letter"] as MaterialTab[]).map(
                        (tab) => (
                          <Button
                            key={tab}
                            size="sm"
                            variant={materialTab === tab ? "default" : "outline"}
                            disabled={!latestByType[tab]}
                            onClick={() => setMaterialTab(tab)}
                          >
                            {materialLabel(tab)}
                          </Button>
                        ),
                      )}
                    </div>
                    {activeMaterial ? (
                      <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs text-muted-foreground">
                            Generated {new Date(activeMaterial.created_at).toLocaleString()}
                            {" · "}
                            {activeMaterial.model_name}
                          </p>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={() => void handleCopy()}>
                              <Copy className="h-3.5 w-3.5" />
                              {copied ? "Copied" : "Copy"}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={downloadLoading}
                              onClick={() => void handleDownload()}
                            >
                              <Download className="h-3.5 w-3.5" />
                              {downloadLoading ? "Downloading…" : "Download PDF"}
                            </Button>
                          </div>
                        </div>
                        <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm text-muted-foreground">
                          {materialDisplayContent(activeMaterial)}
                        </pre>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No {materialLabel(materialTab).toLowerCase()} yet.
                      </p>
                    )}
                  </div>
                </>
              ) : null}

              <Separator />

              <div className="space-y-3">
                <p className="text-sm font-medium">Quick actions</p>
                {hasActiveResume === false ? (
                  <p className="text-sm text-muted-foreground">
                    Upload and activate a resume on the{" "}
                    <Link href="/resume" className="text-primary hover:underline">
                      Resume page
                    </Link>{" "}
                    before generating tailored materials.
                  </p>
                ) : null}
                {actionError ? (
                  <p className="text-sm text-destructive">{actionError}</p>
                ) : null}
                {actionSuccess ? (
                  <div className="space-y-1">
                    <p className="flex items-center gap-1.5 text-sm text-green-700">
                      <CheckCircle2 className="h-4 w-4" />
                      {actionSuccess}
                    </p>
                    {lastAgentExecutionId ? (
                      <Link
                        href={`/agent-runs?execution_id=${lastAgentExecutionId}`}
                        className="text-sm text-primary underline-offset-4 hover:underline"
                      >
                        View agent run
                      </Link>
                    ) : null}
                  </div>
                ) : null}
                {linkedApplication ? (
                  <p className="text-sm text-muted-foreground">
                    Application tracked in stage{" "}
                    <span className="font-medium text-foreground">
                      {linkedApplication.stage}
                    </span>
                    .{" "}
                    <Link href="/applications" className="text-primary hover:underline">
                      View Kanban
                    </Link>
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading !== null}
                    onClick={handleResearch}
                  >
                    {actionLoading === "research" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Research Company
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading !== null}
                    onClick={handleEvaluate}
                  >
                    {actionLoading === "evaluate" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Evaluate Match
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading !== null || hasActiveResume === false}
                    onClick={handleTailorResume}
                  >
                    {actionLoading === "tailor" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Tailor Resume
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading !== null || hasActiveResume === false}
                    onClick={handleCoverLetter}
                  >
                    {actionLoading === "cover_letter" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Cover Letter
                  </Button>
                  <Button
                    size="sm"
                    variant="default"
                    disabled={actionLoading !== null || linkedApplication !== null}
                    onClick={handleMarkApplied}
                  >
                    {actionLoading === "mark_applied" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    {linkedApplication ? "Application tracked" : "Mark applied"}
                  </Button>
                  {showInterviewPrep ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={actionLoading !== null}
                      onClick={handleInterviewPrep}
                    >
                      {actionLoading === "interview_prep" ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <MessageSquare className="h-4 w-4" />
                      )}
                      Interview prep
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={actionLoading !== null || opportunity.status === "saved"}
                    onClick={() => handleStatus("saved")}
                  >
                    {actionLoading === "save" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={actionLoading !== null || opportunity.status === "rejected"}
                    onClick={() => handleStatus("rejected")}
                  >
                    {actionLoading === "reject" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : null}
                    Reject
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}
