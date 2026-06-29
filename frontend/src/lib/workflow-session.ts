export const ACTIVE_WORKFLOW_KEY = "careerpilot:activeWorkflowId";

export function persistActiveWorkflowId(id: string): void {
  if (typeof window !== "undefined") {
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, id);
  }
}

export function getStoredActiveWorkflowId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ACTIVE_WORKFLOW_KEY);
}

export function clearActiveWorkflowId(): void {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
  }
}

export function workspaceUrl(workflowId: string): string {
  return `/workspace?workflow=${workflowId}`;
}
