"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Building2,
  FileText,
  Loader2,
  MessageSquare,
  X,
} from "lucide-react";

import { formatMatchScore } from "@/components/opportunities/opportunity-utils";
import { STAGE_LABELS, STAGE_ORDER } from "@/components/applications/application-utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Separator } from "@/components/ui/separator";
import {
  applicationsApi,
  ApiError,
  type Application,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface ApplicationDetailPanelProps {
  applicationId: string | null;
  onClose: () => void;
  onUpdated?: (application: Application) => void;
}

export function ApplicationDetailPanel({
  applicationId,
  onClose,
  onUpdated,
}: ApplicationDetailPanelProps) {
  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [prepLoading, setPrepLoading] = useState(false);
  const [notes, setNotes] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const open = applicationId !== null;

  const loadDetail = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await applicationsApi.detail(id);
      setApplication(data);
      setNotes(data.notes ?? "");
      setFollowUp(
        data.target_follow_up_at
          ? data.target_follow_up_at.slice(0, 10)
          : "",
      );
    } catch {
      setError("Failed to load application.");
      setApplication(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!applicationId) {
      setApplication(null);
      setError(null);
      setActionMessage(null);
      return;
    }
    void loadDetail(applicationId);
  }, [applicationId, loadDetail]);

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

  const handleStageChange = async (stage: string) => {
    if (!application || stage === application.stage) return;
    setSaving(true);
    setActionMessage(null);
    try {
      const updated = await applicationsApi.update(application.id, {
        stage,
        stage_notes: `Moved to ${STAGE_LABELS[stage] ?? stage}`,
      });
      setApplication(updated);
      onUpdated?.(updated);
      setActionMessage(`Stage updated to ${STAGE_LABELS[stage] ?? stage}.`);
    } catch (err) {
      setActionMessage(
        err instanceof ApiError ? err.message : "Failed to update stage.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotes = async () => {
    if (!application) return;
    setSaving(true);
    setActionMessage(null);
    try {
      const updated = await applicationsApi.update(application.id, {
        notes,
        target_follow_up_at: followUp ? `${followUp}T12:00:00Z` : null,
      });
      setApplication(updated);
      onUpdated?.(updated);
      setActionMessage("Application details saved.");
    } catch (err) {
      setActionMessage(
        err instanceof ApiError ? err.message : "Failed to save details.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleInterviewPrep = async () => {
    if (!application) return;
    setPrepLoading(true);
    setActionMessage(null);
    try {
      const result = await applicationsApi.generateInterviewPrep(application.id);
      setActionMessage(result.reasoning_summary);
      await loadDetail(application.id);
    } catch (err) {
      setActionMessage(
        err instanceof ApiError ? err.message : "Failed to generate interview prep.",
      );
    } finally {
      setPrepLoading(false);
    }
  };

  const matchScore = formatMatchScore(application?.match_score);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50 transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Application details"
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-xl transition-transform",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <p className="text-sm font-medium text-muted-foreground">Application</p>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading...
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : application ? (
            <div className="space-y-6">
              <div className="space-y-2">
                <h2 className="text-xl font-semibold">{application.job_title}</h2>
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Building2 className="h-4 w-4" />
                  {application.job_company}
                  {matchScore ? ` · ${matchScore}` : ""}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/opportunities?selected=${application.opportunity.id}`}>
                      View opportunity
                    </Link>
                  </Button>
                  {application.interview_plans?.[0] ? (
                    <Button asChild size="sm" variant="outline">
                      <Link href={`/interviews?selected=${application.interview_plans[0].id}`}>
                        Latest prep plan
                      </Link>
                    </Button>
                  ) : null}
                </div>
              </div>

              <Separator />

              <div className="space-y-3">
                <Label htmlFor="app-stage">Stage</Label>
                <NativeSelect
                  id="app-stage"
                  className="h-9"
                  value={application.stage}
                  disabled={saving}
                  onChange={(event) => void handleStageChange(event.target.value)}
                >
                  {STAGE_ORDER.map((stage) => (
                    <option key={stage} value={stage}>
                      {STAGE_LABELS[stage]}
                    </option>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-3">
                <Label htmlFor="app-notes">Notes</Label>
                <textarea
                  id="app-notes"
                  className="min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                />
                <Label htmlFor="app-follow-up">Follow-up date</Label>
                <Input
                  id="app-follow-up"
                  type="date"
                  value={followUp}
                  onChange={(event) => setFollowUp(event.target.value)}
                />
                <Button size="sm" disabled={saving} onClick={() => void handleSaveNotes()}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Save details
                </Button>
              </div>

              {application.stage_events && application.stage_events.length > 0 ? (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Stage history</p>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      {application.stage_events.map((event) => (
                        <li
                          key={event.id}
                          className="rounded-lg border border-border px-3 py-2"
                        >
                          <p className="font-medium text-foreground">
                            {event.from_stage
                              ? `${STAGE_LABELS[event.from_stage] ?? event.from_stage} → `
                              : ""}
                            {STAGE_LABELS[event.to_stage] ?? event.to_stage}
                          </p>
                          <p className="text-xs">
                            {new Date(event.created_at).toLocaleString()}
                          </p>
                          {event.notes ? <p>{event.notes}</p> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                </>
              ) : null}

              {application.materials && application.materials.length > 0 ? (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="flex items-center gap-1.5 text-sm font-medium">
                      <FileText className="h-4 w-4" />
                      Materials ({application.materials.length})
                    </p>
                  </div>
                </>
              ) : null}

              <Separator />

              <div className="space-y-2">
                <Button
                  size="sm"
                  disabled={prepLoading}
                  onClick={() => void handleInterviewPrep()}
                >
                  {prepLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <MessageSquare className="h-4 w-4" />
                  )}
                  Generate interview prep
                </Button>
                {actionMessage ? (
                  <p className="text-sm text-muted-foreground">{actionMessage}</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}
