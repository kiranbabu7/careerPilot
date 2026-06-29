"use client";

import type { Application } from "@/lib/api";

import { ApplicationCard } from "./application-card";
import { STAGE_LABELS } from "./application-utils";

interface ApplicationColumnProps {
  stage: string;
  applications: Application[];
  onSelect: (id: string) => void;
}

export function ApplicationColumn({
  stage,
  applications,
  onSelect,
}: ApplicationColumnProps) {
  return (
    <section className="flex min-w-[260px] max-w-[300px] flex-1 flex-col rounded-xl border border-border bg-muted/20">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">{STAGE_LABELS[stage] ?? stage}</h2>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {applications.length}
        </span>
      </header>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        {applications.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            No applications
          </p>
        ) : (
          applications.map((application) => (
            <ApplicationCard
              key={application.id}
              application={application}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </section>
  );
}
