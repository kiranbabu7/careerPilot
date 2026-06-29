"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Briefcase, Building2, X } from "lucide-react";

import {
  CompanyResearchDisplay,
  CompanyResearchHeading,
} from "@/components/companies/company-research-display";
import { hasCompanyResearch } from "@/components/opportunities/opportunity-utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { companyOpportunitiesHref } from "@/components/companies/company-utils";
import type { CompanySummary } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CompanyDetailSheetProps {
  company: CompanySummary | null;
  onClose: () => void;
}

export function CompanyDetailSheet({ company, onClose }: CompanyDetailSheetProps) {
  const open = company !== null;
  const research = company?.latest_research;
  const showResearch = hasCompanyResearch(research);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50 transition-opacity duration-200",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden={!open}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Company details"
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-xl transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <p className="text-sm font-medium text-muted-foreground">Company details</p>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {company ? (
            <div className="space-y-5">
              <div className="space-y-2">
                <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
                  <Building2 className="h-5 w-5 text-muted-foreground" />
                  {company.name}
                </h2>
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Briefcase className="h-4 w-4" />
                  {company.opportunity_count} opportunit
                  {company.opportunity_count === 1 ? "y" : "ies"}
                </p>
              </div>

              {showResearch && research ? (
                <div className="space-y-3">
                  <CompanyResearchHeading />
                  <CompanyResearchDisplay research={research} />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No research available yet. Run company research from an opportunity.
                </p>
              )}

              {company.opportunity_ids.length > 0 ? (
                <>
                  <Separator />
                  <Link
                    href={companyOpportunitiesHref(company.name)}
                    className="inline-flex text-sm font-medium text-primary hover:underline"
                  >
                    View related opportunities
                  </Link>
                </>
              ) : null}
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}
