"use client";

import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { ApiError, interviewsApi, type CreateInterviewPayload } from "@/lib/api";
import { cn } from "@/lib/utils";

interface InterviewFormPanelProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
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

export function InterviewFormPanel({ open, onClose, onCreated }: InterviewFormPanelProps) {
  const [company, setCompany] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [roundLabel, setRoundLabel] = useState("");
  const [format, setFormat] = useState("video");
  const [outcome, setOutcome] = useState("scheduled");
  const [interviewerNotes, setInterviewerNotes] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setCompany("");
    setJobTitle("");
    setScheduledAt("");
    setRoundLabel("");
    setFormat("video");
    setOutcome("scheduled");
    setInterviewerNotes("");
    setJobDescription("");
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!company.trim() || !jobTitle.trim()) {
      setError("Company and job title are required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    const payload: CreateInterviewPayload = {
      company: company.trim(),
      job_title: jobTitle.trim(),
      round_label: roundLabel.trim(),
      format,
      outcome,
      interviewer_notes: interviewerNotes.trim(),
      job_description: jobDescription.trim(),
    };
    if (scheduledAt) {
      payload.scheduled_at = new Date(scheduledAt).toISOString();
    }

    try {
      await interviewsApi.create(payload);
      reset();
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add interview.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={handleClose}
      />
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l border-border bg-background shadow-xl transition-transform",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Plus className="h-4 w-4" />
            Add interview
          </div>
          <Button variant="ghost" size="icon" onClick={handleClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-1 flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
            <div className="space-y-2">
              <Label htmlFor="interview-company">Company</Label>
              <Input
                id="interview-company"
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                placeholder="Acme Corp"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="interview-title">Job title</Label>
              <Input
                id="interview-title"
                value={jobTitle}
                onChange={(event) => setJobTitle(event.target.value)}
                placeholder="Staff Engineer"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="interview-when">Date & time</Label>
              <Input
                id="interview-when"
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="interview-round">Round</Label>
              <Input
                id="interview-round"
                value={roundLabel}
                onChange={(event) => setRoundLabel(event.target.value)}
                placeholder="Technical 1"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="interview-format">Format</Label>
                <NativeSelect
                  id="interview-format"
                  value={format}
                  onChange={(event) => setFormat(event.target.value)}
                >
                  {FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="interview-outcome">Outcome</Label>
                <NativeSelect
                  id="interview-outcome"
                  value={outcome}
                  onChange={(event) => setOutcome(event.target.value)}
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
              <Label htmlFor="interview-notes">Interviewer notes</Label>
              <textarea
                id="interview-notes"
                value={interviewerNotes}
                onChange={(event) => setInterviewerNotes(event.target.value)}
                rows={3}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Hiring manager, panel members, topics to expect..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="interview-jd">Job description (optional)</Label>
              <textarea
                id="interview-jd"
                value={jobDescription}
                onChange={(event) => setJobDescription(event.target.value)}
                rows={4}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Paste a JD to improve prep quality..."
              />
            </div>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add interview"}
            </Button>
          </div>
        </form>
      </aside>
    </>
  );
}
