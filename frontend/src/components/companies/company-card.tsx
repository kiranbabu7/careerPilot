"use client";

import Link from "next/link";
import { Briefcase, Building2, ChevronRight } from "lucide-react";

import {
  CompanyResearchDisplay,
  CompanyResearchHeading,
} from "@/components/companies/company-research-display";
import { hasCompanyResearch } from "@/components/opportunities/opportunity-utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { companyOpportunitiesHref } from "@/components/companies/company-utils";
import type { CompanySummary } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CompanyCardProps {
  company: CompanySummary;
  onSelect: (company: CompanySummary) => void;
}

export function CompanyCard({ company, onSelect }: CompanyCardProps) {
  const research = company.latest_research;
  const showResearch = hasCompanyResearch(research);

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(company)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(company);
        }
      }}
      className={cn(
        "flex cursor-pointer flex-col border-border/80 bg-card/80 transition-colors",
        "hover:border-primary/40 hover:bg-card hover:shadow-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <CardHeader className="space-y-2 p-5 pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          {company.name}
        </CardTitle>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Briefcase className="h-3.5 w-3.5" />
          {company.opportunity_count} opportunit
          {company.opportunity_count === 1 ? "y" : "ies"}
        </p>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 p-5 pt-0">
        {showResearch && research ? (
          <div className="space-y-2">
            <CompanyResearchHeading compact />
            <div className="scrollbar-hide max-h-52 overflow-y-auto pr-1">
              <CompanyResearchDisplay research={research} compact />
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No research available yet. Run company research from an opportunity.
          </p>
        )}

        {company.opportunity_ids.length > 0 ? (
          <Link
            href={companyOpportunitiesHref(company.name)}
            onClick={(event) => event.stopPropagation()}
            className="text-xs font-medium text-primary hover:underline"
          >
            View related opportunities
          </Link>
        ) : null}

        <p className="mt-auto flex items-center gap-1 pt-2 text-xs font-medium text-primary">
          View details
          <ChevronRight className="h-3.5 w-3.5" />
        </p>
      </CardContent>
    </Card>
  );
}
