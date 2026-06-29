"use client";

import { Building2, Calendar, Clock } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ScheduledInterviewSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

const OUTCOME_STYLES: Record<string, string> = {
  scheduled: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
  completed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  cancelled: "bg-muted text-muted-foreground",
  passed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  rejected: "bg-destructive/15 text-destructive",
};

interface InterviewScheduledCardProps {
  interview: ScheduledInterviewSummary;
  onSelect: (id: string) => void;
}

export function InterviewScheduledCard({
  interview,
  onSelect,
}: InterviewScheduledCardProps) {
  const when = interview.scheduled_at
    ? new Date(interview.scheduled_at).toLocaleString()
    : "Date not set";

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(interview.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(interview.id);
        }
      }}
      className="cursor-pointer transition-colors hover:border-primary/40 hover:shadow-sm"
    >
      <CardHeader className="space-y-1 p-4 pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base font-semibold">{interview.job_title}</CardTitle>
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
              OUTCOME_STYLES[interview.outcome] ?? OUTCOME_STYLES.scheduled,
            )}
          >
            {interview.outcome}
          </span>
        </div>
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Building2 className="h-3.5 w-3.5" />
          {interview.job_company}
        </p>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        <p className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          {when}
        </p>
        <p className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {interview.round_label || "Interview"}
          {interview.format ? ` · ${interview.format.replace("_", " ")}` : ""}
        </p>
      </CardContent>
    </Card>
  );
}
