import type { AgentExecution } from "@/lib/api";

export const AGENT_LABELS: Record<string, string> = {
  planner: "Planner",
  job_search: "Job Search",
  company_research: "Company Research",
  job_evaluation: "Job Evaluation",
  resume_tailor: "Resume Tailor",
  cover_letter: "Cover Letter",
  interview_prep: "Interview Prep",
  decision: "Decision Agent",
};

export const AGENT_FILTER_OPTIONS = Object.entries(AGENT_LABELS).map(
  ([value, label]) => ({ value, label }),
);

export const STATUS_FILTER_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "running", label: "Running" },
  { value: "failed", label: "Failed" },
  { value: "pending", label: "Pending" },
  { value: "skipped", label: "Skipped" },
];

export function agentLabel(execution: AgentExecution): string {
  return execution.agent_label ?? AGENT_LABELS[execution.agent_name] ?? execution.agent_name;
}

export function formatDurationMs(durationMs?: number | null): string | null {
  if (durationMs == null) return null;
  if (durationMs < 1000) return `${durationMs}ms`;
  return `${(durationMs / 1000).toFixed(1)}s`;
}

export function formatDuration(execution: AgentExecution): string | null {
  if (execution.duration_ms != null) {
    return formatDurationMs(execution.duration_ms);
  }
  if (!execution.started_at || !execution.completed_at) return null;
  const ms =
    new Date(execution.completed_at).getTime() -
    new Date(execution.started_at).getTime();
  return formatDurationMs(ms);
}

export function statusTone(status: string): string {
  if (status === "completed") return "text-green-700 bg-green-50 border-green-200";
  if (status === "failed") return "text-destructive bg-destructive/10 border-destructive/20";
  if (status === "running" || status === "pending") {
    return "text-primary bg-primary/10 border-primary/20";
  }
  return "text-muted-foreground bg-muted border-border";
}

export function urgencyTone(urgency: string): string {
  if (urgency === "high") return "text-destructive bg-destructive/10";
  if (urgency === "medium") return "text-amber-700 bg-amber-50";
  return "text-muted-foreground bg-muted";
}
