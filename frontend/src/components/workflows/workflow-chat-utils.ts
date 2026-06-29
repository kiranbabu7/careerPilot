import type { WorkflowActionCard, WorkflowMessage } from "@/lib/api";

export function actionsMatch(
  left: WorkflowActionCard,
  right: WorkflowActionCard,
): boolean {
  return (
    left.key === right.key &&
    JSON.stringify(left.params ?? {}) === JSON.stringify(right.params ?? {})
  );
}

/** Remove a consumed action from one assistant message. */
export function clearConsumedAction(
  messages: WorkflowMessage[],
  messageId: string,
  action: WorkflowActionCard,
): WorkflowMessage[] {
  return messages.map((message) => {
    if (message.id !== messageId) return message;
    const remaining = message.actions.filter((item) => !actionsMatch(item, action));
    if (remaining.length === message.actions.length) return message;
    return { ...message, actions: remaining };
  });
}

/** Clear all pending actions from assistant messages (text "yes" confirmation). */
export function clearAllPendingActions(
  messages: WorkflowMessage[],
): WorkflowMessage[] {
  return messages.map((message) =>
    message.role === "assistant" && message.actions.length > 0
      ? { ...message, actions: [] }
      : message,
  );
}

export function findLatestAssistantWithActions(
  messages: WorkflowMessage[],
): WorkflowMessage | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "assistant" && message.actions.length > 0) {
      return message;
    }
  }
  return null;
}
