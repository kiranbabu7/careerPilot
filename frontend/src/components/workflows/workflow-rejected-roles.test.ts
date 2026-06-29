import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WorkflowRejectedRoles } from "@/components/workflows/workflow-rejected-roles";

vi.mock("@/lib/api", () => ({
  opportunitiesApi: {
    list: vi.fn(),
  },
}));

describe("WorkflowRejectedRoles", () => {
  it("renders nothing when rejected count is zero", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowRejectedRoles, {
        workflowId: "wf-1",
        rejectedCount: 0,
      }),
    );

    expect(html).toBe("");
  });

  it("shows view rejected controls when roles exist", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowRejectedRoles, {
        workflowId: "wf-2",
        rejectedCount: 2,
      }),
    );

    expect(html).toContain("2 rejected roles from evaluation");
    expect(html).toContain("View 2 rejected");
    expect(html).toContain("/opportunities?workflow_id=wf-2&amp;filter=rejected");
  });
});
