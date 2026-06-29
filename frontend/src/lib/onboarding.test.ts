import { describe, expect, it } from "vitest";

import type { DashboardSummary } from "@/lib/api";
import {
  getOnboardingSteps,
  needsOnboarding,
  parseLocationInput,
} from "@/lib/onboarding";

function dashboardWithMissing(keys: string[]): DashboardSummary {
  const all = [
    "target_roles",
    "locations",
    "career_goals",
    "skills",
    "salary",
    "resume",
    "resume_analysis",
  ];
  const missing = new Set(keys);
  return {
    profile_completion: 0,
    completion_signals: {
      completed: all
        .filter((key) => !missing.has(key))
        .map((key) => ({ key, label: key, weight: 10 })),
      missing: [...missing].map((key) => ({ key, label: key, weight: 10 })),
    },
    active_resume: null,
    preferences_summary: {
      target_roles: [],
      target_locations: [],
      remote_preference: "flexible",
      skills_count: 0,
      has_career_goals: false,
    },
    recent_activity: [],
    next_actions: [],
  };
}

describe("parseLocationInput", () => {
  it("maps Flexible quick reply to remote_preference flexible", () => {
    expect(parseLocationInput("Flexible")).toEqual({
      remote_preference: "flexible",
      target_locations: [],
    });
  });
});

describe("needsOnboarding", () => {
  it("returns false when only optional salary step remains", () => {
    const dashboard = dashboardWithMissing(["salary"]);
    expect(needsOnboarding(dashboard)).toBe(false);
  });

  it("returns true when required profile fields are still missing", () => {
    const dashboard = dashboardWithMissing(["career_goals", "salary"]);
    expect(needsOnboarding(dashboard)).toBe(true);
  });

  it("returns false when all required onboarding steps are complete", () => {
    const dashboard = dashboardWithMissing([]);
    expect(needsOnboarding(dashboard)).toBe(false);
  });
});

describe("getOnboardingSteps", () => {
  it("drops remote_preference once locations signal is complete", () => {
    const steps = getOnboardingSteps(dashboardWithMissing(["skills", "salary"]));
    expect(steps).not.toContain("remote_preference");
    expect(steps).toEqual(["skills", "salary", "complete"]);
  });

  it("includes remote_preference while locations signal is missing", () => {
    const steps = getOnboardingSteps(dashboardWithMissing(["locations", "skills"]));
    expect(steps).toContain("remote_preference");
  });
});
