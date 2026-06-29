import { describe, expect, it } from "vitest";

import {
  actionsMatch,
  clearAllPendingActions,
  clearConsumedAction,
  findLatestAssistantWithActions,
} from "@/components/workflows/workflow-chat-utils";
import type { WorkflowActionCard, WorkflowMessage } from "@/lib/api";

const tailorAction: WorkflowActionCard = {
  key: "tailor_resume",
  label: "Tailor resume for best match",
  description: "Generate a tailored resume.",
  params: { pick: "best" },
  requires_confirmation: true,
  endpoint_hint: "actions/tailor_resume",
};

const coverAction: WorkflowActionCard = {
  key: "cover_letter",
  label: "Generate cover letter",
  description: "Draft a cover letter.",
  params: { pick: "best" },
  requires_confirmation: true,
  endpoint_hint: "actions/cover_letter",
};

function assistantMessage(
  id: string,
  actions: WorkflowActionCard[] = [],
): WorkflowMessage {
  return {
    id,
    role: "assistant",
    content: "Ready when you are.",
    actions,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("workflow chat utils", () => {
  it("matches actions by key and params", () => {
    expect(actionsMatch(tailorAction, { ...tailorAction })).toBe(true);
    expect(
      actionsMatch(tailorAction, {
        ...tailorAction,
        params: { pick: "other" },
      }),
    ).toBe(false);
  });

  it("clears only the consumed action from one message", () => {
    const messages = [
      assistantMessage("assistant-1", [tailorAction, coverAction]),
      assistantMessage("assistant-2", [tailorAction]),
    ];

    const next = clearConsumedAction(messages, "assistant-1", tailorAction);

    expect(next[0]?.actions).toEqual([coverAction]);
    expect(next[1]?.actions).toEqual([tailorAction]);
  });

  it("clears all assistant pending actions after text confirmation", () => {
    const messages = [
      assistantMessage("assistant-1", [tailorAction]),
      {
        id: "user-1",
        role: "user" as const,
        content: "yes",
        actions: [],
        created_at: "2026-01-01T00:00:01Z",
      },
      assistantMessage("assistant-2", [coverAction]),
    ];

    const next = clearAllPendingActions(messages);

    expect(next[0]?.actions).toEqual([]);
    expect(next[2]?.actions).toEqual([]);
  });

  it("finds the latest assistant message that still has actions", () => {
    const messages = [
      assistantMessage("assistant-1", [tailorAction]),
      assistantMessage("assistant-2", []),
      assistantMessage("assistant-3", [coverAction]),
    ];

    expect(findLatestAssistantWithActions(messages)?.id).toBe("assistant-3");
  });
});
