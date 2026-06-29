import type { DashboardSummary } from "@/lib/api";

export type OnboardingStep =
  | "welcome"
  | "career_goals"
  | "target_roles"
  | "remote_preference"
  | "resume"
  | "skills"
  | "salary"
  | "complete";

/** Steps that are prompted but not required to finish profile setup. */
const OPTIONAL_ONBOARDING_STEPS: ReadonlySet<OnboardingStep> = new Set([
  "welcome",
  "salary",
  "complete",
]);

export function needsOnboarding(dashboard: DashboardSummary): boolean {
  return getOnboardingSteps(dashboard).some(
    (step) => !OPTIONAL_ONBOARDING_STEPS.has(step),
  );
}

export function isProfileCleared(dashboard: DashboardSummary): boolean {
  const missing = new Set(
    dashboard.completion_signals.missing.map((signal) => signal.key),
  );
  return missing.has("career_goals") && missing.has("target_roles");
}

const GAP_STEPS: { key: string; step: OnboardingStep }[] = [
  { key: "career_goals", step: "career_goals" },
  { key: "target_roles", step: "target_roles" },
  { key: "locations", step: "remote_preference" },
  { key: "skills", step: "skills" },
  { key: "salary", step: "salary" },
];

export const UPLOAD_RESUME_QUICK_REPLY = "Upload resume";

export function resumeIsMissing(dashboard: DashboardSummary): boolean {
  return dashboard.completion_signals.missing.some((signal) => signal.key === "resume");
}

export function getOnboardingSteps(dashboard: DashboardSummary): OnboardingStep[] {
  const missing = new Set(
    dashboard.completion_signals.missing.map((signal) => signal.key),
  );
  const steps: OnboardingStep[] = [];

  if (missing.has("resume") || isProfileCleared(dashboard)) {
    steps.push("welcome", "resume");
  }
  for (const { key, step } of GAP_STEPS) {
    if (missing.has(key)) steps.push(step);
  }
  steps.push("complete");

  return steps;
}

export function getInitialOnboardingStep(dashboard: DashboardSummary): OnboardingStep {
  return getOnboardingSteps(dashboard)[0] ?? "complete";
}

/** Steps that should not be re-prompted when resuming onboarding with an existing resume. */
export function skippedResumePromptSteps(dashboard: DashboardSummary): OnboardingStep[] {
  if (resumeIsMissing(dashboard) || isProfileCleared(dashboard)) return [];
  return ["welcome", "resume"];
}

export function postResumeSummary(dashboard: DashboardSummary): string {
  const completed = new Set(
    dashboard.completion_signals.completed.map((signal) => signal.key),
  );
  const extracted: string[] = [];
  if (completed.has("skills")) extracted.push("skills");
  if (completed.has("target_roles")) extracted.push("target roles");
  if (completed.has("career_goals")) extracted.push("career goals");

  const remainingGaps = dashboard.completion_signals.missing.filter((signal) =>
    GAP_STEPS.some(({ key }) => key === signal.key),
  );

  if (extracted.length > 0 && remainingGaps.length === 0) {
    return "Your resume gave me everything I need — profile's looking good!";
  }
  if (extracted.length > 0) {
    return `Nice — I pulled ${extracted.join(", ")} from your resume. Just a few quick questions left to round things out.`;
  }
  return "Thanks — I've saved your resume. A few quick questions will help me personalize your experience.";
}

export function parseTags(text: string): string[] {
  return text
    .split(/[,;]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function titleCaseLocation(part: string): string {
  return part
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function matchRemotePreference(part: string): string | null {
  const normalized = part.trim().toLowerCase();
  const match = REMOTE_QUICK_REPLIES.find(
    (opt) => opt.label.toLowerCase() === normalized || opt.value === normalized,
  );
  return match?.value ?? null;
}

export function parseLocationInput(text: string): {
  remote_preference?: string;
  target_locations: string[];
} {
  const parts = parseTags(text);
  let remote_preference: string | undefined;
  const target_locations: string[] = [];

  for (const part of parts) {
    const remote = matchRemotePreference(part);
    if (remote) {
      remote_preference = remote;
      continue;
    }
    target_locations.push(titleCaseLocation(part));
  }

  return { remote_preference, target_locations };
}

function parseSalaryAmount(token: string): number | null {
  const part = token.trim().toLowerCase();
  if (!part) return null;

  const lakhWord = part.match(/^(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac)$/);
  if (lakhWord) return Math.round(parseFloat(lakhWord[1]) * 100_000);

  const suffixed = part.match(/^(\d+(?:\.\d+)?)\s*(l(?:pa)?|k)$/);
  if (suffixed) {
    const numeric = parseFloat(suffixed[1]);
    if (suffixed[2].startsWith("l")) return Math.round(numeric * 100_000);
    return Math.round(numeric * 1_000);
  }

  const plain = part.match(/^(\d+(?:\.\d+)?)$/);
  if (plain) return Math.round(parseFloat(plain[1]));

  return null;
}

function normalizeSalaryText(text: string): string {
  return text
    .replace(/\$/g, "")
    .replace(/,/g, "")
    .replace(/\b(?:lakhs?|lacs?|lac)\b/gi, "l")
    .replace(/\s+/g, " ")
    .trim();
}

function hasExplicitUnit(token: string): boolean {
  const part = token.trim().toLowerCase();
  return /(?:^|\d)\s*(?:l(?:pa)?|k|lakhs?|lacs?|lac)$/i.test(part);
}

export function parseSalaryInput(
  text: string,
): { salary_min: number | null; salary_max: number | null } | null {
  const trimmed = text.trim();
  if (!trimmed || /^skip$/i.test(trimmed)) return null;

  const normalized = normalizeSalaryText(trimmed);
  const rangeParts = normalized.split(/\s*(?:-|–|—|\bto\b)\s*/i).filter(Boolean);

  if (rangeParts.length >= 2) {
    const maxPart = rangeParts[1];
    let minPart = rangeParts[0];
    if (!hasExplicitUnit(minPart) && hasExplicitUnit(maxPart)) {
      const sharedUnit = maxPart.match(/(l(?:pa)?|k)$/i)?.[1];
      if (sharedUnit) minPart = `${minPart}${sharedUnit}`;
    }

    const salary_min = parseSalaryAmount(minPart);
    const salary_max = parseSalaryAmount(maxPart);
    if (salary_min === null) return null;
    return { salary_min, salary_max: salary_max ?? null };
  }

  const salary_min = parseSalaryAmount(normalized);
  if (salary_min === null) return null;
  return { salary_min, salary_max: null };
}

export function usesInrSalaryContext(
  salaryMin: number | null,
  salaryMax: number | null,
): boolean {
  const values = [salaryMin, salaryMax].filter((value): value is number => value !== null);
  return values.some((value) => value >= 100_000);
}

export function formatSalaryInrHint(amount: number | null): string {
  if (amount === null) return "";
  if (amount >= 100_000 && amount % 100_000 === 0) {
    return `${amount / 100_000}L`;
  }
  if (amount >= 1_000 && amount % 1_000 === 0 && amount < 100_000) {
    return `${amount / 1_000}K`;
  }
  return amount.toLocaleString("en-IN");
}

export const REMOTE_QUICK_REPLIES = [
  { label: "Remote only", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "On-site", value: "onsite" },
  { label: "Flexible", value: "flexible" },
] as const;

export function stepPrompt(
  step: OnboardingStep,
  userName?: string,
): string {
  const greeting = userName ? `Hi ${userName.split(" ")[0]}! ` : "Hi! ";

  switch (step) {
    case "welcome":
      return `${greeting}I'm your CareerPilot teammate. Upload your resume and I'll extract your skills and experience first — then we'll only cover what's still missing. Ready?`;
    case "career_goals":
      return "What does your next career move look like? Tell me what success means for you — role level, industry, timeline, anything that matters.";
    case "target_roles":
      return "Which job titles are you targeting? List a few (comma-separated works), e.g. Senior Backend Engineer, Staff Engineer.";
    case "remote_preference":
      return "What's your work location preference? You can pick an option below or type cities you'd consider.";
    case "resume":
      return "Upload your resume and I'll extract your skills and experience first. PDF, DOCX, or TXT — attach it here or use the clip icon below.";
    case "skills":
      return "Any key skills you want me to highlight? List them comma-separated, or say skip if your resume already covers it.";
    case "salary":
      return "What's your target salary range? Share min and max (e.g. 26L-30L, 26-30L, 50K, 120k-180k, or 120000-180000), or skip for now.";
    case "complete":
      return "You're all set! Your profile is ready — taking you to Home so you can plan your next career goal.";
  }
}
