import { describe, expect, it } from "vitest";

import type { WorkflowActionCard } from "@/lib/api";

function actionLabel(action: WorkflowActionCard): string {
  return `${action.label} (${action.key})`;
}

describe("workflow action cards", () => {
  it("formats action label with key", () => {
    const action: WorkflowActionCard = {
      key: "rerun_job_search",
      label: "Rerun job search",
      description: "Run job discovery again with updated filters.",
      params: { remote_preference: "remote" },
      requires_confirmation: true,
      endpoint_hint: "actions/rerun_job_search",
    };

    expect(actionLabel(action)).toBe("Rerun job search (rerun_job_search)");
    expect(action.requires_confirmation).toBe(true);
  });
});
