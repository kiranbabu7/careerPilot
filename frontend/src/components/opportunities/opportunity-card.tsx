"use client";

import {
  Building2,
  ExternalLink,
  MapPin,
  Newspaper,
  Sparkles,
  Wifi,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Opportunity } from "@/lib/api";

function formatSalary(job: Opportunity["job"]): string | null {
  const { salary_min, salary_max, salary_currency } = job;
  if (!salary_min && !salary_max) return null;
  const currency = salary_currency || "USD";
  const fmt = (v: string) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(Number(v));
  if (salary_min && salary_max && salary_min !== salary_max) {
    return `${fmt(salary_min)} – ${fmt(salary_max)}`;
  }
  return fmt(salary_min || salary_max || "0");
}

export function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
  const { job } = opportunity;
  const salary = formatSalary(job);
  const research = job.company_research;
  const hasResearch = research?.available && (research.summary || research.snippets?.length);

  return (
    <Card className="flex flex-col border-border/80 bg-card/80 transition-colors hover:border-primary/30">
      <CardHeader className="space-y-2 p-5 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-base font-semibold leading-snug">
              {job.title}
            </CardTitle>
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Building2 className="h-3.5 w-3.5 shrink-0" />
              {job.company}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs font-medium capitalize text-muted-foreground">
            {job.source}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {job.location ? (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {job.location}
            </span>
          ) : null}
          {job.is_remote ? (
            <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
              <Wifi className="h-3 w-3" />
              Remote
            </span>
          ) : null}
          {salary ? <span>{salary}</span> : null}
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3 p-5 pt-0">
        {job.description ? (
          <p className="line-clamp-3 text-sm text-muted-foreground">{job.description}</p>
        ) : null}

        {opportunity.match_context ? (
          <div className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
            <p className="mb-0.5 flex items-center gap-1 text-xs font-medium text-primary">
              <Sparkles className="h-3 w-3" />
              Why this match
            </p>
            <p className="text-muted-foreground">{opportunity.match_context}</p>
          </div>
        ) : null}

        {hasResearch ? (
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
            <p className="mb-1 flex items-center gap-1 text-xs font-medium">
              <Newspaper className="h-3 w-3" />
              Company research
            </p>
            {research.summary ? (
              <p className="text-muted-foreground">{research.summary}</p>
            ) : null}
            {research.snippets?.slice(0, 2).map((snippet) => (
              <p key={snippet.url} className="mt-1 text-xs text-muted-foreground">
                {snippet.snippet}
              </p>
            ))}
          </div>
        ) : null}

        <div className="mt-auto flex flex-wrap gap-2 pt-2">
          {job.apply_url ? (
            <Button asChild size="sm">
              <a href={job.apply_url} target="_blank" rel="noopener noreferrer">
                Apply
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Button>
          ) : null}
          <Button size="sm" variant="outline" disabled title="Available in Phase 5">
            Research Company
          </Button>
          <Button size="sm" variant="outline" disabled title="Available in Phase 6">
            Tailor Resume
          </Button>
          <Button size="sm" variant="ghost" disabled title="Available in Phase 5">
            Save
          </Button>
          <Button size="sm" variant="ghost" disabled title="Available in Phase 5">
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
