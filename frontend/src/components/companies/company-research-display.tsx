"use client";

import { Newspaper } from "lucide-react";

import type { Job } from "@/lib/api";
import { companyResearchSections } from "@/components/opportunities/opportunity-utils";

interface CompanyResearchDisplayProps {
  research: NonNullable<Job["company_research"]>;
  compact?: boolean;
}

export function CompanyResearchDisplay({
  research,
  compact = false,
}: CompanyResearchDisplayProps) {
  const sections = companyResearchSections(research);
  const snippetLimit = compact ? 2 : undefined;

  return (
    <div className="space-y-3">
      {sections.map((section) => (
        <div key={section.key} className="space-y-1">
          <p
            className={
              compact
                ? "text-xs font-medium"
                : "text-sm font-medium"
            }
          >
            {section.label}
          </p>
          <p
            className={
              compact
                ? "text-sm leading-relaxed text-muted-foreground"
                : "text-sm leading-relaxed text-muted-foreground"
            }
          >
            {section.value}
          </p>
        </div>
      ))}

      {research.snippets && research.snippets.length > 0 ? (
        <div className="space-y-2">
          {!compact ? (
            <p className="text-sm font-medium">Sources</p>
          ) : null}
          {(snippetLimit
            ? research.snippets.slice(0, snippetLimit)
            : research.snippets
          ).map((snippet, index) => (
            <div
              key={`${snippet.category}-${snippet.url}-${index}`}
              className="rounded-lg border border-border bg-muted/30 px-3 py-2"
            >
              {snippet.title ? (
                <a
                  href={snippet.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={
                    compact
                      ? "text-xs font-medium text-primary hover:underline"
                      : "text-sm font-medium text-primary hover:underline"
                  }
                >
                  {snippet.title}
                </a>
              ) : null}
              <p
                className={
                  compact
                    ? "mt-0.5 line-clamp-2 text-xs text-muted-foreground"
                    : "mt-1 text-sm text-muted-foreground"
                }
              >
                {snippet.snippet}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function CompanyResearchHeading({ compact = false }: { compact?: boolean }) {
  return (
    <p
      className={
        compact
          ? "flex items-center gap-1 text-xs font-medium"
          : "flex items-center gap-1.5 text-sm font-medium"
      }
    >
      <Newspaper className={compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
      Company research
    </p>
  );
}
