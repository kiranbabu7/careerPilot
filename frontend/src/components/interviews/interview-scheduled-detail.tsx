"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Building2, Loader2, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Separator } from "@/components/ui/separator";
import {
  ApiError,
  interviewsApi,
  type ScheduledInterview,
  type UpdateInterviewPayload,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface InterviewScheduledDetailProps {
  interviewId: string | null;
  onClose: () => void;
  onUpdated?: () => void;
  onPrepGenerated?: (planId: string) => void;
}

const FORMAT_OPTIONS = [
  { value: "video", label: "Video" },
  { value: "phone", label: "Phone" },
  { value: "onsite", label: "Onsite" },
  { value: "take_home", label: "Take home" },
  { value: "other", label: "Other" },
];

const OUTCOME_OPTIONS = [
  { value: "scheduled", label: "Scheduled" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "passed", label: "Passed" },
  { value: "rejected", label: "Rejected" },
];

function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
}

export function InterviewScheduledDetail({
  interviewId,
  onClose,
  onUpdated,
  onPrepGenerated,
}: InterviewScheduledDetailProps) {
  const [interview, setInterview] = useState<ScheduledInterview | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [prepLoading, setPrepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = interviewId !== null;

  const loadInterview = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await interviewsApi.detail(id);
      if (data.type !== "scheduled") {
        setError("This item is a prep plan, not a scheduled interview.");
        setInterview(null);
        return;
      }
      setInterview(data);
    } catch {
      setError("Failed to load interview.");
      setInterview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!interviewId) {
      setInterview(null);
      setError(null);
      return;
    }
    void loadInterview(interviewId);
  }, [interviewId, loadInterview]);

  const handleSave = async () => {
    if (!interview) return;
    setSaving(true);
    setError(null);
    const payload: UpdateInterviewPayload = {
      round_label: interview.round_label,
      format: interview.format,
      outcome: interview.outcome,
      interviewer_notes: interview.interviewer_notes,
      job_description: interview.job_description,
      scheduled_at: interview.scheduled_at,
    };
    try {
      const updated = await interviewsApi.update(interview.id, payload);
      setInterview(updated);
      onUpdated?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save interview.");
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePrep = async () => {
    if (!interview) return;
    setPrepLoading(true);
    setError(null);
    try {
      const result = await interviewsApi.generateInterviewPrep(interview.id);
      onPrepGenerated?.(result.interview_plan.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate prep.");
    } finally {
      setPrepLoading(false);
    }
  };

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l border-border bg-background shadow-xl transition-transform",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <p className="text-sm font-medium text-muted-foreground">Interview details</p>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading interview...
            </div>
          ) : error && !interview ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : interview ? (
            <div className="space-y-5">
              <div className="space-y-1">
                <h2 className="text-xl font-semibold">{interview.job_title}</h2>
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Building2 className="h-4 w-4" />
                  {interview.job_company}
                </p>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="detail-when">Date & time</Label>
                  <Input
                    id="detail-when"
                    type="datetime-local"
                    value={toLocalInputValue(interview.scheduled_at)}
                    onChange={(event) =>
                      setInterview({
                        ...interview,
                        scheduled_at: event.target.value
                          ? new Date(event.target.value).toISOString()
                          : null,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="detail-round">Round</Label>
                  <Input
                    id="detail-round"
                    value={interview.round_label}
                    onChange={(event) =>
                      setInterview({ ...interview, round_label: event.target.value })
                    }
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="detail-format">Format</Label>
                    <NativeSelect
                      id="detail-format"
                      value={interview.format}
                      onChange={(event) =>
                        setInterview({ ...interview, format: event.target.value })
                      }
                    >
                      {FORMAT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="detail-outcome">Outcome</Label>
                    <NativeSelect
                      id="detail-outcome"
                      value={interview.outcome}
                      onChange={(event) =>
                        setInterview({ ...interview, outcome: event.target.value })
                      }
                    >
                      {OUTCOME_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="detail-notes">Interviewer notes</Label>
                  <textarea
                    id="detail-notes"
                    value={interview.interviewer_notes}
                    onChange={(event) =>
                      setInterview({ ...interview, interviewer_notes: event.target.value })
                    }
                    rows={3}
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="detail-jd">Job description</Label>
                  <textarea
                    id="detail-jd"
                    value={interview.job_description}
                    onChange={(event) =>
                      setInterview({ ...interview, job_description: event.target.value })
                    }
                    rows={4}
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
              </div>

              {error ? <p className="text-sm text-destructive">{error}</p> : null}

              <Separator />

              <div className="flex flex-wrap gap-2">
                <Button size="sm" disabled={saving} onClick={() => void handleSave()}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save changes"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={prepLoading}
                  onClick={() => void handleGeneratePrep()}
                >
                  {prepLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  Generate prep
                </Button>
                {interview.application_id ? (
                  <Button asChild size="sm" variant="outline">
                    <Link href="/applications">Application</Link>
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}
