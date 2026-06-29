import { describe, expect, it } from "vitest";

import { topFactorSummary } from "@/components/opportunities/match-factor-breakdown";
import type { OpportunityEvaluation } from "@/lib/api";

const evaluation: OpportunityEvaluation = {
  match_score: 82,
  recommendation: "strong_match",
  rationale: "Strong fit overall.",
  strengths: ["Role aligns"],
  gaps: [],
  factors: {
    role_match: { score: 90, weight: 0.25, detail: "Title aligns well." },
    skill_overlap: { score: 80, weight: 0.25, detail: "Matched 4 of 5 skills." },
  },
  agent_execution_id: "exec-123",
};

describe("topFactorSummary", () => {
  it("returns the highest-scoring factor label", () => {
    expect(topFactorSummary(evaluation)).toBe("Role match (90/100)");
  });

  it("returns null when no factors exist", () => {
    expect(topFactorSummary({ ...evaluation, factors: {} })).toBeNull();
  });
});
