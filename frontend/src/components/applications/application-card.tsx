"use client";

import { Building2, Calendar, FileText, Target } from "lucide-react";

import { formatMatchScore } from "@/components/opportunities/opportunity-utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Application } from "@/lib/api";
import { cn } from "@/lib/utils";

import { STAGE_LABELS } from "./application-utils";

interface ApplicationCardProps {
  application: Application;
  onSelect: (id: string) => void;
}

export function ApplicationCard({ application, onSelect }: ApplicationCardProps) {
  const matchScore = formatMatchScore(application.match_score);
  const notesPreview = application.notes?.trim();
  const followUp = application.target_follow_up_at
    ? new Date(application.target_follow_up_at).toLocaleDateString()
    : null;

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(application.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(application.id);
        }
      }}
      className={cn(
        "cursor-pointer border-border/80 bg-card/90 transition-colors",
        "hover:border-primary/40 hover:shadow-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <CardHeader className="space-y-2 p-4 pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 space-y-1">
            <CardTitle className="truncate text-sm font-semibold">
              {application.job_title}
            </CardTitle>
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              <Building2 className="h-3 w-3 shrink-0" />
              <span className="truncate">{application.job_company}</span>
            </p>
          </div>
          {matchScore ? (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
              <Target className="h-3 w-3" />
              {matchScore}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1">
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {STAGE_LABELS[application.stage] ?? application.stage}
          </span>
          {application.has_tailored_resume ? (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-800">
              Resume
            </span>
          ) : null}
          {application.has_cover_letter ? (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-800">
              Cover
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        {followUp ? (
          <p className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            Follow up {followUp}
          </p>
        ) : null}
        {notesPreview ? (
          <p className="flex items-start gap-1 line-clamp-2">
            <FileText className="mt-0.5 h-3 w-3 shrink-0" />
            {notesPreview}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
