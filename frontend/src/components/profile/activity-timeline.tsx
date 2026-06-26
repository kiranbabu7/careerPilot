import { FileText, Settings, Sparkles } from "lucide-react";

import type { ActivityEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ActivityTimelineProps {
  events: ActivityEvent[];
  className?: string;
}

function eventIcon(eventType: string) {
  switch (eventType) {
    case "resume_uploaded":
    case "resume_analyzed":
      return FileText;
    case "preferences_updated":
      return Settings;
    default:
      return Sparkles;
  }
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString();
}

export function ActivityTimeline({ events, className }: ActivityTimelineProps) {
  if (events.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        No activity yet. Upload a resume or update your preferences to get started.
      </p>
    );
  }

  return (
    <ul className={cn("space-y-4", className)}>
      {events.map((event) => {
        const Icon = eventIcon(event.event_type);
        return (
          <li key={event.id} className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
              <Icon className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm font-medium">{event.title}</p>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatTime(event.created_at)}
                </span>
              </div>
              {event.description ? (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {event.description}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
