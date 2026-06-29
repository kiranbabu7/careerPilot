import { describe, expect, it } from "vitest";

import type { CompanySummary, Opportunity } from "@/lib/api";

import {
  companyHasOpportunities,
  companyOpportunitiesHref,
  normalizeCompanyName,
  opportunityMatchesCompany,
} from "./company-utils";

function makeOpportunity(company: string): Opportunity {
  return {
    id: "opp-1",
    job: {
      id: "job-1",
      external_id: "ext-1",
      source: "test",
      title: "Engineer",
      company,
      location: "Remote",
      is_remote: true,
      salary_min: null,
      salary_max: null,
      salary_currency: "USD",
      description: "",
      apply_url: "",
      posted_at: null,
      company_research: {},
      created_at: "",
      updated_at: "",
    },
    status: "discovered",
    source_agent: "job_search",
    match_context: "",
    match_score: 80,
    evaluation: {},
    created_at: "",
  };
}

describe("company-utils", () => {
  it("builds encoded company opportunities href", () => {
    expect(companyOpportunitiesHref("AT&T")).toBe(
      "/opportunities?company=AT%26T",
    );
  });

  it("matches company names case-insensitively", () => {
    expect(
      opportunityMatchesCompany(makeOpportunity("Acme Corp"), "acme corp"),
    ).toBe(true);
    expect(
      opportunityMatchesCompany(makeOpportunity(" Acme Corp "), "Acme Corp"),
    ).toBe(true);
  });

  it("detects companies with opportunities", () => {
    const withOpportunities: CompanySummary = {
      name: "Acme",
      opportunity_count: 2,
      opportunity_ids: ["1", "2"],
      latest_research: {},
      has_research: false,
    };
    const withoutOpportunities: CompanySummary = {
      ...withOpportunities,
      opportunity_count: 0,
      opportunity_ids: [],
    };

    expect(companyHasOpportunities(withOpportunities)).toBe(true);
    expect(companyHasOpportunities(withoutOpportunities)).toBe(false);
  });

  it("normalizes company names", () => {
    expect(normalizeCompanyName("  Stripe  ")).toBe("stripe");
  });
});
