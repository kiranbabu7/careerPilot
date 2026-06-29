import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  WorkflowIntentCallout,
  formatIntentReason,
} from "@/components/workflows/workflow-intent-callout";
import type { IntentClassification, WorkflowDetail } from "@/lib/api";

describe("formatIntentReason", () => {
  it("includes matched phrase when present", () => {
    const classification: IntentClassification = {
      intent: "tailor_resume",
      method: "rule_based",
      matched_phrase: "tailor my resume",
      planned_agents: ["planner"],
    };
    expect(formatIntentReason(classification)).toContain("tailor my resume");
    expect(formatIntentReason(classification)).toContain("Resume tailoring");
  });

  it("describes default routing when no phrase matched", () => {
    const classification: IntentClassification = {
      intent: "job_discovery",
      method: "rule_based",
      matched_phrase: null,
      planned_agents: ["planner", "job_search", "job_evaluation"],
    };
    expect(formatIntentReason(classification)).toContain("Default routing");
    expect(formatIntentReason(classification)).toContain("Job discovery");
  });
});

describe("WorkflowIntentCallout", () => {
  const classification: IntentClassification = {
    intent: "job_discovery",
    method: "llm",
    matched_phrase: null,
    planned_agents: ["planner", "job_search", "job_evaluation"],
  };

  it("shows extracted constraints and tool choices from agentic planner data", () => {
    const detail = {
      constraints: [
        { key: "role", label: "Role", value: "senior backend" },
        { key: "company_stage", value: "growth-stage startup" },
      ],
      tool_plan: [
        {
          tool: "job_search",
          why: "Find remote senior backend listings.",
        },
        {
          tool: "company_research",
          why: "Verify startup stage before scoring.",
        },
      ],
      user_visible_plan: [
        {
          title: "Find evidence-backed remote backend roles",
          description: "Search, research companies, then evaluate with stage evidence.",
        },
      ],
    } as WorkflowDetail;

    const html = renderToStaticMarkup(
      createElement(WorkflowIntentCallout, { classification, detail }),
    );

    expect(html).toContain("Extracted constraints");
    expect(html).toContain("senior backend");
    expect(html).toContain("Selected tools");
    expect(html).toContain("Verify startup stage");
    expect(html).toContain("Find evidence-backed remote backend roles");
  });

  it("renders replanning events distinctly from the initial plan", () => {
    const detail = {
      tool_plan: [{ tool: "job_search", why: "Initial search." }],
      replan_events: [
        {
          at: "2026-01-01T00:10:00Z",
          action: "insert_tools",
          reason: "Zero strong matches — broadening search.",
          inserted_tools: ["company_research"],
        },
      ],
    } as WorkflowDetail;

    const html = renderToStaticMarkup(
      createElement(WorkflowIntentCallout, { classification, detail }),
    );

    expect(html).toContain("Replanning");
    expect(html).toContain("broadening search");
    expect(html).toContain("company_research");
  });

  it("uses unique keys when tool_plan repeats the same tool", () => {
    const detail = {
      tool_plan: [
        { tool: "job_search", why: "Find roles." },
        { tool: "job_evaluation", why: "Initial scoring." },
        { tool: "company_research", why: "Verify company stage." },
        { tool: "job_evaluation", why: "Re-score with research." },
      ],
    } as WorkflowDetail;

    const html = renderToStaticMarkup(
      createElement(WorkflowIntentCallout, { classification, detail }),
    );

    expect(html).toContain("Initial scoring");
    expect(html).toContain("Re-score with research");
    expect((html.match(/job_evaluation/g) ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it("falls back to planned agents when tool_plan is absent", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowIntentCallout, { classification }),
    );

    expect(html).toContain("Planned agents:");
    expect(html).toContain("job_search");
  });
});
