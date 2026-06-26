"use client";

import Link from "next/link";
import { CheckCircle2, Circle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ProfileCompletionCardProps {
  dashboard: DashboardSummary;
}

export function ProfileCompletionCard({ dashboard }: ProfileCompletionCardProps) {
  const { completion_signals, profile_completion, active_resume, next_actions } = dashboard;

  return (
    <Card className="border-primary/20 bg-card/80">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Your profile</CardTitle>
        <p className="text-sm text-muted-foreground">
          Upload your resume and CareerPilot will finish your profile from it.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Overall progress</span>
            <span className="font-medium">{profile_completion}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${profile_completion}%` }}
            />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <SignalList
            title="Completed"
            items={completion_signals.completed}
            variant="completed"
          />
          <SignalList
            title="Still needed"
            items={completion_signals.missing}
            variant="missing"
          />
        </div>

        {active_resume ? (
          <div className="rounded-lg border border-border p-3 text-sm">
            <p className="font-medium">{active_resume.original_filename}</p>
            <p className="text-muted-foreground">
              Health {active_resume.health_score ?? "—"} · ATS{" "}
              {active_resume.ats_score ?? "—"}
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No active resume yet — upload one to unlock AI analysis and profile
            enrichment.
          </p>
        )}

        {next_actions.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">Suggested next step</p>
            {next_actions.slice(0, 2).map((action) => (
              <Link
                key={action.key}
                href={action.href}
                className="block rounded-lg border border-border px-4 py-3 text-sm transition-colors hover:border-primary/40 hover:bg-muted/30"
              >
                <p className="font-medium">{action.title}</p>
                <p className="text-muted-foreground">{action.description}</p>
              </Link>
            ))}
          </div>
        ) : null}

        {profile_completion < 100 ? (
          <Button asChild variant="outline" size="sm">
            <Link href="/resume">Upload resume</Link>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SignalList({
  title,
  items,
  variant,
}: {
  title: string;
  items: Array<{ key: string; label: string }>;
  variant: "completed" | "missing";
}) {
  const Icon = variant === "completed" ? CheckCircle2 : Circle;

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li
              key={item.key}
              className={cn(
                "flex items-center gap-2 text-sm",
                variant === "completed" ? "text-foreground" : "text-muted-foreground",
              )}
            >
              <Icon
                className={cn(
                  "h-3.5 w-3.5 shrink-0",
                  variant === "completed" ? "text-emerald-500" : "text-muted-foreground",
                )}
              />
              {item.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
