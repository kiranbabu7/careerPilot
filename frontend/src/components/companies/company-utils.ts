import type { CompanySummary, Opportunity } from "@/lib/api";

export function normalizeCompanyName(name: string): string {
  return name.trim().toLowerCase();
}

export function companyHasOpportunities(company: CompanySummary): boolean {
  return company.opportunity_count > 0 && company.opportunity_ids.length > 0;
}

export function companyOpportunitiesHref(companyName: string): string {
  return `/opportunities?company=${encodeURIComponent(companyName)}`;
}

export function opportunityMatchesCompany(
  opportunity: Opportunity,
  companyName: string,
): boolean {
  return (
    normalizeCompanyName(opportunity.job.company) ===
    normalizeCompanyName(companyName)
  );
}
