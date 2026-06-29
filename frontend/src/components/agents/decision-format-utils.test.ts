import { describe, expect, it } from "vitest";

import {
  formatEvidenceValue,
  resolveDecisionActionRoute,
  textValue,
} from "@/components/agents/decision-format-utils";

describe("decision-format-utils", () => {
  it("formats primitive evidence values", () => {
    expect(textValue("hello")).toBe("hello");
    expect(formatEvidenceValue("summary", 3)).toEqual(["3"]);
  });

  it("formats opportunity evidence items", () => {
    const lines = formatEvidenceValue("top_opportunities", [
      { title: "Engineer", company: "Acme", match_score: 88, status: "saved" },
    ]);
    expect(lines[0]).toContain("Engineer");
    expect(lines[0]).toContain("Acme");
    expect(lines[0]).toContain("88/100");
  });

  it("returns None for empty arrays", () => {
    expect(formatEvidenceValue("applications", [])).toEqual(["None"]);
  });

  it("resolves tailor resume actions to workspace goal URLs", () => {
    expect(
      resolveDecisionActionRoute({
        action_type: "material",
        target_id: "11111111-1111-4111-8111-111111111111",
        title: "Generate tailored resume for Senior Software Engineer at Recro",
        route: "/opportunities/11111111-1111-4111-8111-111111111111/tailor-resume",
      }),
    ).toBe(
      "/workspace?goal=Tailor%20my%20resume%20for%20Senior%20Software%20Engineer%20at%20Recro",
    );
  });

  it("resolves invalid opportunity paths to selected query params", () => {
    expect(
      resolveDecisionActionRoute({
        action_type: "opportunity",
        target_id: "22222222-2222-4222-8222-222222222222",
        title: "Review role",
        route: "/opportunities/22222222-2222-4222-8222-222222222222",
      }),
    ).toBe("/opportunities?selected=22222222-2222-4222-8222-222222222222");
  });
});
