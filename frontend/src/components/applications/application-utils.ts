export const STAGE_LABELS: Record<string, string> = {
  draft: "Draft",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const STAGE_ORDER = [
  "draft",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
] as const;

export const PRIORITY_LABELS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};
