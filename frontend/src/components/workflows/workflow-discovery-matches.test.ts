import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WorkflowDiscoveryMatches } from "@/components/workflows/workflow-discovery-matches";

vi.mock("@/lib/api", () => ({
  opportunitiesApi: {
    list: vi.fn(),
  },
}));

describe("WorkflowDiscoveryMatches", () => {
  it("shows View matches when high-match roles exist", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowDiscoveryMatches, {
        workflowId: "wf-1",
        discoveredCount: 4,
        evaluatedCount: 4,
        acceptedCount: 2,
      }),
    );

    expect(html).toContain("4 roles discovered");
    expect(html).toContain("4 evaluated");
    expect(html).toContain("2 high match");
    expect(html).toContain("View 2 matches");
    expect(html).toContain("/opportunities?workflow_id=wf-1&amp;filter=high_match");
  });

  it("shows View roles when evaluated but no high matches", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowDiscoveryMatches, {
        workflowId: "wf-2",
        discoveredCount: 4,
        evaluatedCount: 4,
        acceptedCount: 0,
      }),
    );

    expect(html).toContain("4 roles discovered");
    expect(html).toContain("4 evaluated");
    expect(html).not.toContain("high match");
    expect(html).toContain("View 4 roles");
    expect(html).toContain("/opportunities?workflow_id=wf-2&amp;filter=all");
  });

  it("renders nothing when no discovery activity", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowDiscoveryMatches, {
        workflowId: "wf-3",
        discoveredCount: 0,
        evaluatedCount: 0,
        acceptedCount: 0,
      }),
    );

    expect(html).toBe("");
  });

  it("shows View roles when only discovered count is hydrated", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowDiscoveryMatches, {
        workflowId: "wf-4",
        discoveredCount: 3,
        evaluatedCount: 0,
        acceptedCount: 0,
      }),
    );

    expect(html).toContain("3 roles discovered");
    expect(html).toContain("View 3 roles");
    expect(html).toContain("/opportunities?workflow_id=wf-4&amp;filter=all");
  });
});
