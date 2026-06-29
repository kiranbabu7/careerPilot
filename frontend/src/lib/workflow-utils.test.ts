import { describe, expect, it } from "vitest";

import type { AgentExecution, WorkflowDetail, WorkflowMessage } from "@/lib/api";
import {
  buildFallbackQuickReplies,
    buildPipelineSteps,
    deriveQuickRepliesFromActions,
    deriveWorkflowQuickReplies,
    findLatestTailorSelectionMessageId,
    formatConstraintLabel,
    formatInterviewPrepTargetSource,
    formatReplanEvent,
    formatToolProgressEvent,
    getToolPlanStep,
    interviewPrepNextAction,
    isLinkOnlyWorkflowAction,
    isSearchRerunActive,
    jobDiscoveryCompletionMessage,
    parseTailorSelectionMetadata,
    pipelineExecutionsForDisplay,
    resolveActiveToolProgress,
    resolveAgenticPlannerData,
  resolveActiveCoverLetterMaterialId,
  resolveActiveTailoredMaterialId,
  resolveActiveTailorSelection,
  resolveIntentClassification,
  shouldRenderMaterialActionInFooter,
  shouldShowTailorSelectorInChat,
    suggestedNextStepLabels,
  } from "@/lib/workflow-utils";

function execution(
  agentName: string,
  status: string,
  overrides: Partial<AgentExecution> = {},
): AgentExecution {
  return {
    id: `${agentName}-${status}`,
    workflow_execution: "wf-1",
    agent_name: agentName,
    status,
    reasoning_summary: "",
    error_message: "",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: status === "completed" ? "2026-01-01T00:01:00Z" : null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function detail(
  status: string,
  agentExecutions: AgentExecution[],
  overrides: Partial<WorkflowDetail> = {},
): WorkflowDetail {
  return {
    workflow: {
      id: "wf-1",
      name: "Test",
      goal: "Test goal",
      status,
      context: {},
      result: {},
      started_at: "2026-01-01T00:00:00Z",
      completed_at: null,
      error_message: "",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    agent_executions: agentExecutions,
    plan_summary: "",
    suggested_steps: [],
    discovered_count: 0,
    provider_summary: { providers: {} },
    job_search_summary: "",
    evaluated_count: 0,
    accepted_count: 0,
    rejected_count: 0,
    top_match_score: 0,
    ...overrides,
  };
}

describe("buildPipelineSteps", () => {
  it("uses planned_agents to hide job search for tailor-only workflows", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [execution("planner", "completed", { reasoning_summary: "Tailor plan ready" })],
        {
          workflow_intent: "tailor_resume",
          planned_agents: ["planner"],
          next_action: "Select a saved or high-match role below to tailor your resume.",
          tailor_selection_pending: true,
        },
      ),
      false,
    );

    expect(steps.map((step) => step.key)).toEqual(["planner", "select_role"]);
    expect(steps.some((step) => step.key === "job_search")).toBe(false);
  });

  it("shows only planned discovery pipeline agents", () => {
    const steps = buildPipelineSteps(
      detail("running", [execution("planner", "running")], {
        planned_agents: ["planner", "job_search", "job_evaluation"],
      }),
      true,
    );

    expect(steps.map((step) => step.key)).toEqual(["planner", "job_search", "job_evaluation"]);
  });

  it("shows planner and role selection for tailor resume intent", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [execution("planner", "completed", { reasoning_summary: "Tailor plan ready" })],
        {
          workflow_intent: "tailor_resume",
          next_action: "Select a saved or high-match role below to tailor your resume.",
          tailor_selection_pending: true,
        },
      ),
      false,
    );

    expect(steps).toHaveLength(2);
    expect(steps.map((step) => step.key)).toEqual(["planner", "select_role"]);
    expect(steps[0].state).toBe("completed");
    expect(steps[1].state).toBe("pending");
  });

  it("shows resume tailor step only after tailoring runs", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [
          execution("planner", "completed", { reasoning_summary: "Tailor plan ready" }),
          execution("resume_tailor", "completed", {
            reasoning_summary: "Tailored resume for Staff Engineer at FinCo.",
          }),
        ],
        {
          workflow_intent: "tailor_resume",
          tailor_selection_pending: false,
          tailored_material_id: "mat-1",
        },
      ),
      false,
    );

    expect(steps.map((step) => step.key)).toEqual(["planner", "resume_tailor"]);
    expect(steps[1].state).toBe("completed");
  });

  it("shows interview prep pipeline agents when plan is ready", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [
          execution("planner", "completed", { reasoning_summary: "Prep plan ready" }),
          execution("interview_prep", "completed", {
            reasoning_summary: "Generated system design prep plan.",
          }),
        ],
        {
          workflow_intent: "interview_prep",
          planned_agents: ["planner", "interview_prep"],
          interview_plan_id: "plan-1",
          next_action: "General interview prep plan ready for your goal.",
        },
      ),
      false,
    );

    expect(steps.map((step) => step.key)).toEqual(["planner", "interview_prep"]);
    expect(steps[1].state).toBe("completed");
  });

  it("shows interview prep target source in pipeline detail", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [
          execution("planner", "completed", { reasoning_summary: "Prep plan ready" }),
          execution("interview_prep", "completed", {
            reasoning_summary: "Generated resume revision prep plan.",
          }),
        ],
        {
          workflow_intent: "interview_prep",
          planned_agents: ["planner", "interview_prep"],
          interview_plan_id: "plan-1",
          interview_prep_target_source: "general",
          next_action: "Resume-based interview prep plan ready.",
        },
      ),
      false,
    );

    expect(steps[1].detail).toContain("resume and goal");
    expect(interviewPrepNextAction({
      next_action: "Resume-based interview prep plan ready.",
      interview_prep_target_source: "general",
    } as WorkflowDetail)).toContain("Target:");
    expect(formatInterviewPrepTargetSource("application")).toContain("application pipeline");
  });

  it("shows planner running while other steps stay pending", () => {
    const steps = buildPipelineSteps(
      detail("running", [execution("planner", "running")]),
      true,
    );

    expect(steps.map((step) => step.state)).toEqual(["running", "pending", "pending"]);
  });

  it("shows job search running only after planner completes", () => {
    const steps = buildPipelineSteps(
      detail("running", [
        execution("planner", "completed", { reasoning_summary: "Plan ready" }),
        execution("job_search", "running"),
      ]),
      true,
    );

    expect(steps[0].state).toBe("completed");
    expect(steps[1].state).toBe("running");
    expect(steps[2].state).toBe("pending");
  });

  it("shows evaluation running with partial counts before workflow result catches up", () => {
    const steps = buildPipelineSteps(
      detail(
        "running",
        [
          execution("planner", "completed"),
          execution("job_search", "completed", {
            output_data: { discovered_count: 3 },
          }),
          execution("job_evaluation", "completed", {
            reasoning_summary: "Evaluated role A",
          }),
          execution("job_evaluation", "running", {
            input_data: { job_title: "Backend Engineer" },
          }),
        ],
        { discovered_count: 3 },
      ),
      true,
    );

    expect(steps[2].state).toBe("running");
    expect(steps[2].detail).toContain("Backend Engineer");
  });

  it("does not mark all steps completed until each agent finishes", () => {
    const steps = buildPipelineSteps(
      detail(
        "running",
        [
          execution("planner", "completed"),
          execution("job_search", "running"),
        ],
      ),
      true,
    );

    expect(steps.map((step) => step.state)).toEqual(["completed", "running", "pending"]);
  });

  it("keeps evaluation pending while job search is still running", () => {
    const steps = buildPipelineSteps(
      detail(
        "running",
        [
          execution("planner", "completed"),
          execution("job_search", "running"),
          execution("job_evaluation", "completed", {
            reasoning_summary: "Stale backlog evaluation",
          }),
        ],
        { evaluated_count: 2, discovered_count: 1 },
      ),
      true,
    );

    expect(steps[1].state).toBe("running");
    expect(steps[2].state).toBe("pending");
  });
});

describe("jobDiscoveryCompletionMessage", () => {
  it("labels backlog re-evaluation when nothing new was discovered", () => {
    const message = jobDiscoveryCompletionMessage(
      detail("completed", [], {
        discovered_count: 0,
        evaluated_count: 1,
        accepted_count: 1,
        top_match_score: 82,
      }),
    );

    expect(message).toBe("Re-evaluated 1 backlog role — 1 high match");
  });

  it("reports newly discovered high matches when discovery succeeded", () => {
    const message = jobDiscoveryCompletionMessage(
      detail("completed", [], {
        discovered_count: 2,
        evaluated_count: 2,
        accepted_count: 1,
        top_match_score: 90,
      }),
    );

    expect(message).toBe("Found 1 high-match role");
  });
});

describe("workflow quick replies", () => {
  it("maps assistant action cards to trigger phrases", () => {
    const replies = deriveQuickRepliesFromActions([
      {
        key: "list_applications",
        label: "List applications",
        description: "Show pipeline",
        params: {},
        requires_confirmation: true,
        endpoint_hint: "",
      },
      {
        key: "generate_interview_prep",
        label: "Generate interview prep",
        description: "Prep plan",
        params: {},
        requires_confirmation: true,
        endpoint_hint: "",
      },
    ]);

    expect(replies).toEqual([
      { label: "List applications", value: "List my applications" },
      { label: "Generate interview prep", value: "Generate interview prep" },
    ]);
  });

  it("excludes link-only material and prep view actions from quick replies", () => {
    const replies = deriveQuickRepliesFromActions([
      {
        key: "view_tailored_resume",
        label: "View tailored resume",
        description: "Preview resume",
        params: { material_id: "mat-1" },
        requires_confirmation: false,
        endpoint_hint: "",
      },
      {
        key: "download_tailored_resume",
        label: "Download PDF",
        description: "Download resume",
        params: { material_id: "mat-1" },
        requires_confirmation: false,
        endpoint_hint: "",
      },
      {
        key: "tailor_resume",
        label: "Tailor resume for best match",
        description: "Run tailor",
        params: { pick: "best" },
        requires_confirmation: true,
        endpoint_hint: "",
      },
    ]);

    expect(replies).toEqual([
      { label: "Tailor resume for best match", value: "tailor resume" },
    ]);
    expect(isLinkOnlyWorkflowAction({
      key: "view_tailored_resume",
      label: "View tailored resume",
      description: "",
      params: { material_id: "mat-1" },
      requires_confirmation: false,
      endpoint_hint: "",
    })).toBe(true);
  });

  it("builds job-discovery fallbacks when no discoveries", () => {
    const replies = buildFallbackQuickReplies(
      detail("completed", [], { discovered_count: 0 }),
    );

    expect(replies.map((reply) => reply.label)).toEqual([
      "Rerun search",
      "List applications",
      "Interview prep",
      "What can you do?",
    ]);
  });

  it("prefers latest assistant actions over workflow fallbacks", () => {
    const workflowDetail = detail("completed", [], {
      discovered_count: 0,
    });
    const messages: WorkflowMessage[] = [
      {
        id: "m1",
        role: "assistant",
        content: "Here are next steps",
        actions: [
          {
            key: "show_rejected",
            label: "Show rejected roles",
            description: "Include rejected",
            params: {},
            requires_confirmation: true,
            endpoint_hint: "",
          },
        ],
        created_at: "2026-01-01T00:00:00Z",
      },
    ];

    const replies = deriveWorkflowQuickReplies(messages, workflowDetail);

    expect(replies).toEqual([
      { label: "Show rejected roles", value: "Show rejected roles" },
    ]);
  });

  it("exposes completion summary labels without help chip", () => {
    const labels = suggestedNextStepLabels(
      detail("completed", [], { discovered_count: 2, accepted_count: 1 }),
    );

    expect(labels).toContain("Rerun search");
    expect(labels).not.toContain("What can you do?");
  });
});

describe("resolveIntentClassification", () => {
  it("reads intent classification from workflow result", () => {
    const classification = resolveIntentClassification(
      detail("running", [], {
        workflow: {
          id: "wf-1",
          name: "Test",
          goal: "Tailor my resume",
          status: "running",
          context: {},
          result: {
            intent_classification: {
              intent: "tailor_resume",
              method: "rule_based",
              matched_phrase: "tailor my resume",
              planned_agents: ["planner"],
            },
          },
          started_at: "2026-01-01T00:00:00Z",
          completed_at: null,
          error_message: "",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      }),
    );

    expect(classification?.intent).toBe("tailor_resume");
    expect(classification?.matched_phrase).toBe("tailor my resume");
  });
});

describe("pipeline reasoning traces", () => {
  it("includes planner and evaluation reasoning entries for discovery workflows", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [
          execution("planner", "completed", { reasoning_summary: "Plan ready" }),
          execution("job_search", "completed", {
            reasoning_summary: "Found 3 roles",
            output_data: { discovered_count: 3 },
          }),
          execution("job_evaluation", "completed", {
            reasoning_summary: "Evaluated Acme role",
            input_data: { job_title: "Backend Engineer" },
            output_data: { match_score: 88 },
          }),
        ],
        {
          planned_agents: ["planner", "job_search", "job_evaluation"],
          discovered_count: 3,
          evaluated_count: 1,
          accepted_count: 1,
          top_match_score: 88,
        },
      ),
      false,
    );

    const planner = steps.find((step) => step.key === "planner");
    const evaluation = steps.find((step) => step.key === "job_evaluation");

    expect(planner?.reasoningTrace?.some((entry) => entry.label === "Workflow intent")).toBe(
      true,
    );
    expect(
      evaluation?.reasoningTrace?.some((entry) => entry.label === "Latest role"),
    ).toBe(true);
  });

  it("shows actionable planner steps instead of repeating plan summary", () => {
    const steps = buildPipelineSteps(
      detail(
        "completed",
        [
          execution("planner", "completed", {
            reasoning_summary: "Will run: planner → job_search → job_evaluation. First action: Discover opportunities.",
            input_data: {
              context: {
                preferences: { target_roles: ["Backend Engineer"], target_locations: ["Remote"] },
                active_resume: { filename: "resume.pdf", health_score: 82 },
                memory_snippets: ["Prefers fintech"],
                pipeline_counts: { applications: 2, materials: 0, interview_plans: 0 },
              },
            },
            output_data: {
              planned_agents: ["planner", "job_search", "job_evaluation"],
              suggested_steps: [
                {
                  key: "discover_opportunities",
                  title: "Discover opportunities",
                  description: "Job search providers scan boards for matching roles.",
                },
              ],
            },
          }),
        ],
        {
          plan_summary: "Planning workflow for: find backend roles. Job search runs automatically...",
          suggested_steps: [
            {
              key: "discover_opportunities",
              title: "Discover opportunities",
              description: "Job search providers scan boards for matching roles.",
            },
          ],
          planned_agents: ["planner", "job_search", "job_evaluation"],
        },
      ),
      false,
    );

    const planner = steps.find((step) => step.key === "planner");
    const labels = planner?.reasoningTrace?.map((entry) => entry.label) ?? [];

    expect(labels).toContain("Target roles");
    expect(labels).toContain("Agents to run");
    expect(labels).toContain("Step 1");
    expect(labels).not.toContain("Plan");
    expect(planner?.reasoningTrace?.some((entry) => entry.label === "Rationale")).toBe(true);
  });

  it("uses agentic planner constraints and tool rationale when present", () => {
    const steps = buildPipelineSteps(
      detail(
        "running",
        [execution("planner", "completed"), execution("job_search", "running")],
        {
          planned_agents: ["planner", "job_search", "company_research", "job_evaluation"],
          constraints: [
            { key: "role", label: "Role", value: "senior backend" },
            { key: "location", value: "remote" },
          ],
          tool_plan: [
            {
              tool: "job_search",
              why: "Find remote senior backend listings across providers.",
              auto_run: true,
            },
            {
              tool: "company_research",
              why: "Verify growth-stage startup signals before scoring.",
              auto_run: true,
            },
            {
              tool: "job_evaluation",
              why: "Score matches using company-stage evidence.",
              auto_run: true,
            },
          ],
          replan_events: [
            {
              at: "2026-01-01T00:05:00Z",
              action: "insert_tools",
              reason: "Company stage evidence required before final scoring.",
              inserted_tools: ["company_research"],
            },
          ],
        },
      ),
      true,
    );

    expect(steps.map((step) => step.key)).toEqual([
      "planner",
      "job_search",
      "company_research",
      "job_evaluation",
    ]);

    const planner = steps.find((step) => step.key === "planner");
    expect(
      planner?.reasoningTrace?.some(
        (entry) => entry.label === "Constraint" && entry.detail.includes("senior backend"),
      ),
    ).toBe(true);
    expect(
      planner?.reasoningTrace?.some(
        (entry) => entry.variant === "replan" && entry.detail.includes("company_research"),
      ),
    ).toBe(true);

    const companyResearch = steps.find((step) => step.key === "company_research");
    expect(companyResearch?.toolRationale).toContain("growth-stage");
  });

  it("reads agentic planner data from workflow.result when top-level fields are missing", () => {
    const data = resolveAgenticPlannerData(
      detail("running", [], {
        workflow: {
          id: "wf-1",
          name: "Test",
          goal: "Find remote backend roles",
          status: "running",
          context: {},
          result: {
            constraints: [{ key: "location", value: "remote" }],
            tool_plan: [{ tool: "job_search", why: "Search boards for remote roles." }],
          },
          started_at: "2026-01-01T00:00:00Z",
          completed_at: null,
          error_message: "",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      }),
    );

    expect(data?.constraints).toHaveLength(1);
    expect(formatConstraintLabel(data!.constraints[0])).toBe("location: remote");
    expect(formatReplanEvent({
      at: "2026-01-01T00:00:00Z",
      action: "insert_tools",
      reason: "Need company research.",
      inserted_tools: ["company_research"],
    })).toContain("company_research");
  });

  it("normalizes dict constraints and tool_plan reason fields from backend", () => {
    const data = resolveAgenticPlannerData(
      detail("completed", [], {
        constraints: {
          location: "remote",
          company_stage: "growth-stage startup",
          requires_company_research: true,
        },
        tool_plan: [
          { tool: "job_search", reason: "Discover matching roles." },
          { tool: "company_research", reason: "Verify startup stage." },
          { tool: "job_evaluation", reason: "Score discovered roles." },
        ],
      }),
    );

    expect(data?.constraints).toHaveLength(2);
    expect(data?.toolPlan.map((step) => step.tool)).toEqual([
      "job_search",
      "company_research",
      "job_evaluation",
    ]);
    expect(getToolPlanStep(
      detail("completed", [], {
        tool_plan: [{ tool: "company_research", reason: "Verify startup stage." }],
      }),
      "company_research",
    )?.why).toBe("Verify startup stage.");
  });
});

describe("workflowRefinementFlags", () => {
  it("reads include_rejected from workflow context", async () => {
    const { workflowRefinementFlags, parseWorkflowRefinementResult } = await import(
      "@/lib/workflow-utils"
    );

    expect(
      workflowRefinementFlags({
        workflow: {
          context: { refinement: { include_rejected: true } },
        },
      } as never).includeRejected,
    ).toBe(true);

    expect(
      parseWorkflowRefinementResult({
        refinement_result: {
          kind: "rejected",
          count: 1,
          opportunities: [{ id: "opp-1" } as never],
        },
      }),
    ).toEqual({
      kind: "rejected",
      count: 1,
      opportunities: [{ id: "opp-1" }],
    });
  });
});

describe("search rerun helpers", () => {
  it("detects active search rerun from workflow detail", () => {
    expect(
      isSearchRerunActive(
        detail("running", [], { search_rerun_in_progress: true }),
      ),
    ).toBe(true);
    expect(isSearchRerunActive(detail("completed", []))).toBe(false);
  });

  it("filters stale pipeline executions during search rerun", () => {
    const executions = [
      execution("job_search", "completed", {
        created_at: "2026-01-01T00:00:00Z",
        started_at: "2026-01-01T00:00:00Z",
      }),
      execution("job_search", "running", {
        id: "job-search-rerun",
        created_at: "2026-01-02T00:00:00Z",
        started_at: "2026-01-02T00:00:00Z",
      }),
    ];
    const activeDetail = detail("running", executions, {
      search_rerun_in_progress: true,
      workflow: {
        id: "wf-1",
        name: "Test",
        goal: "Test goal",
        status: "running",
        context: {},
        result: {
          search_rerun_in_progress: true,
          search_rerun_started_at: "2026-01-02T00:00:00Z",
        },
        started_at: "2026-01-01T00:00:00Z",
        completed_at: null,
        error_message: "",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-02T00:00:00Z",
      },
    });

    const filtered = pipelineExecutionsForDisplay(executions, activeDetail);
    expect(filtered.map((item) => item.id)).toEqual(["job-search-rerun"]);
  });

  it("resets discovery pipeline steps while search rerun is active", () => {
    const steps = buildPipelineSteps(
      detail(
        "running",
        [
          execution("planner", "completed"),
          execution("job_search", "completed", {
            created_at: "2026-01-01T00:00:00Z",
            started_at: "2026-01-01T00:00:00Z",
          }),
        ],
        {
          planned_agents: ["planner", "job_search", "job_evaluation"],
          search_rerun_in_progress: true,
          workflow: {
            id: "wf-1",
            name: "Test",
            goal: "Test goal",
            status: "running",
            context: {},
            result: {
              search_rerun_in_progress: true,
              search_rerun_started_at: "2026-01-02T00:00:00Z",
            },
            started_at: "2026-01-01T00:00:00Z",
            completed_at: null,
            error_message: "",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-02T00:00:00Z",
          },
        },
      ),
      true,
    );

    const jobSearch = steps.find((step) => step.key === "job_search");
    expect(jobSearch?.state).toBe("pending");
  });
});

describe("tailor selection metadata", () => {
  it("parses tailor selection metadata from assistant messages", () => {
    expect(
      parseTailorSelectionMetadata({
        tailor_selection: {
          pending: true,
          tailor_options: { opportunities: [], supports_custom_jd: true },
        },
      }),
    ).toEqual({
      pending: true,
      tailor_options: { opportunities: [], supports_custom_jd: true },
    });
  });

  it("hides tailor selector in chat during search rerun", () => {
    const metadata = parseTailorSelectionMetadata({
      tailor_selection: { pending: true },
    });
    const activeDetail = detail("running", [], {
      tailor_selection_pending: true,
      search_rerun_in_progress: true,
    });

    expect(shouldShowTailorSelectorInChat(activeDetail, metadata)).toBe(false);
    expect(
      shouldShowTailorSelectorInChat(
        detail("completed", [], { tailor_selection_pending: true }),
        metadata,
      ),
    ).toBe(true);
  });

  it("shows tailor selector from message metadata before workflow detail refreshes", () => {
    const metadata = parseTailorSelectionMetadata({
      tailor_selection: {
        pending: true,
        tailor_options: { opportunities: [], supports_custom_jd: true },
      },
    });

    expect(
      shouldShowTailorSelectorInChat(
        detail("completed", [], { tailor_selection_pending: false }),
        metadata,
      ),
    ).toBe(true);
  });

  it("finds the latest assistant message with pending tailor selection", () => {
    const messages: WorkflowMessage[] = [
      {
        id: "older",
        role: "assistant",
        content: "Earlier picker",
        actions: [],
        metadata: { tailor_selection: { pending: true } },
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "latest",
        role: "assistant",
        content: "Current picker",
        actions: [],
        metadata: { tailor_selection: { pending: true } },
        created_at: "2026-01-02T00:00:00Z",
      },
    ];

    expect(findLatestTailorSelectionMessageId(messages)).toBe("latest");
  });

  it("resolves active tailor selection from the latest pending message", () => {
    const tailorOptions = { opportunities: [], supports_custom_jd: true };
    const messages: WorkflowMessage[] = [
      {
        id: "older",
        role: "assistant",
        content: "Earlier picker",
        actions: [],
        metadata: { tailor_selection: { pending: true } },
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "latest",
        role: "assistant",
        content: "Current picker",
        actions: [],
        metadata: {
          tailor_selection: { pending: true, tailor_options: tailorOptions },
        },
        created_at: "2026-01-02T00:00:00Z",
      },
      {
        id: "follow-up",
        role: "assistant",
        content: "Workflow update",
        actions: [],
        metadata: {},
        created_at: "2026-01-03T00:00:00Z",
      },
    ];

    expect(
      resolveActiveTailorSelection(
        messages,
        detail("completed", [], { tailor_selection_pending: true }),
      ),
    ).toEqual({
      pending: true,
      tailor_options: tailorOptions,
    });
  });

  it("returns null when tailor selection is no longer active", () => {
    const messages: WorkflowMessage[] = [
      {
        id: "tailor",
        role: "assistant",
        content: "Pick a role",
        actions: [],
        metadata: { tailor_selection: { pending: true } },
        created_at: "2026-01-01T00:00:00Z",
      },
    ];

    expect(
      resolveActiveTailorSelection(
        messages,
        detail("completed", [], {
          tailor_selection_pending: false,
          tailored_material_id: "material-1",
        }),
      ),
    ).toBeNull();
  });
});

describe("pinned material results", () => {
  it("resolves tailored material id when ready and not in search rerun", () => {
    expect(
      resolveActiveTailoredMaterialId(
        detail("completed", [], { tailored_material_id: "material-1" }),
      ),
    ).toBe("material-1");
    expect(
      resolveActiveTailoredMaterialId(
        detail("running", [], {
          tailored_material_id: "material-1",
          search_rerun_in_progress: true,
        }),
      ),
    ).toBeNull();
  });

  it("resolves cover letter material id when ready", () => {
    expect(
      resolveActiveCoverLetterMaterialId(
        detail("completed", [], { cover_letter_material_id: "letter-1" }),
      ),
    ).toBe("letter-1");
  });

  it("hides material footer actions when material is pinned at bottom", () => {
    const workflowDetail = detail("completed", [], { tailored_material_id: "material-1" });
    expect(
      shouldRenderMaterialActionInFooter(
        {
          key: "view_tailored_resume",
          label: "View tailored resume",
          description: "Preview",
          params: { material_id: "material-1" },
          requires_confirmation: false,
          endpoint_hint: "",
        },
        workflowDetail,
      ),
    ).toBe(false);
    expect(
      shouldRenderMaterialActionInFooter(
        {
          key: "tailor_resume",
          label: "Tailor resume",
          description: "Run tailor",
          params: {},
          requires_confirmation: true,
          endpoint_hint: "actions/tailor_resume",
        },
        workflowDetail,
      ),
    ).toBe(true);
  });
});

describe("tool progress streaming", () => {
  it("formats evaluation and research progress events", () => {
    expect(
      formatToolProgressEvent({
        kind: "job_evaluation",
        job_title: "Backend Engineer",
        company: "Acme",
        match_score: 72,
        recommendation: "borderline_match",
      }),
    ).toBe("Evaluated Backend Engineer at Acme — 72% fit (borderline match)");

    expect(
      formatToolProgressEvent({
        kind: "company_research",
        company: "Acme",
        available: true,
        summary: "Series B fintech.",
      }),
    ).toBe("Researched Acme: Series B fintech.");
  });

  it("surfaces active tool progress in pipeline reasoning traces", () => {
    const steps = buildPipelineSteps(
      detail(
        "running",
        [
          execution("planner", "completed"),
          execution("job_search", "completed"),
          execution("job_evaluation", "running", {
            input_data: { job_title: "Staff Engineer" },
          }),
        ],
        {
          planned_agents: ["planner", "job_search", "job_evaluation"],
          evaluated_count: 1,
          tool_progress: {
            tool: "job_evaluation",
            status: "running",
            current: 1,
            total: 3,
            current_label: "Staff Engineer at GrowthCo",
            recent_events: [
              {
                kind: "job_evaluation",
                job_title: "Backend Engineer",
                company: "Acme",
                match_score: 81,
                recommendation: "strong_match",
              },
            ],
          },
        },
      ),
      true,
    );

    const evaluation = steps.find((step) => step.key === "job_evaluation");
    expect(
      resolveActiveToolProgress(
        detail("running", [], {
          tool_progress: {
            tool: "job_evaluation",
            status: "running",
            current: 1,
            total: 3,
          },
        }),
      ),
    ).not.toBeNull();
    expect(evaluation?.detail).toContain("Staff Engineer at GrowthCo");
    expect(evaluation?.detail).toContain("1/3");
    expect(
      evaluation?.reasoningTrace?.some((entry) => entry.label === "Evaluated"),
    ).toBe(true);
  });
});
