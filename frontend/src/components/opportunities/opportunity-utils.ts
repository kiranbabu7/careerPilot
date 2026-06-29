import type { ApplicationMaterial, Job } from "@/lib/api";

export function formatSalary(job: Job): string | null {
  const { salary_min, salary_max, salary_currency } = job;
  if (!salary_min && !salary_max) return null;
  const currency = salary_currency || "USD";
  const fmt = (v: string) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(Number(v));
  if (salary_min && salary_max && salary_min !== salary_max) {
    return `${fmt(salary_min)} – ${fmt(salary_max)}`;
  }
  return fmt(salary_min || salary_max || "0");
}

export function formatSource(source: string): string {
  if (source === "apify") return "Apify";
  if (source === "linkedin") return "LinkedIn";
  return source.charAt(0).toUpperCase() + source.slice(1);
}

const COMPANY_RESEARCH_SECTION_KEYS = [
  "summary",
  "what_they_do",
  "recent_news",
  "funding",
  "hiring_signals",
] as const;

export function companyResearchSections(
  research: Job["company_research"] | undefined,
): Array<{ key: string; label: string; value: string }> {
  if (!research) return [];

  const labels: Record<(typeof COMPANY_RESEARCH_SECTION_KEYS)[number], string> = {
    summary: "Overview",
    what_they_do: "What they do",
    recent_news: "Recent news",
    funding: "Funding",
    hiring_signals: "Hiring & culture",
  };

  return COMPANY_RESEARCH_SECTION_KEYS.flatMap((key) => {
    const value = research[key]?.trim();
    if (!value) return [];
    return [{ key, label: labels[key], value }];
  });
}

export function hasCompanyResearch(
  research: Job["company_research"] | undefined,
): boolean {
  return Boolean(
    research?.available &&
      (companyResearchSections(research).length > 0 ||
        research.snippets?.length),
  );
}

export const HIGH_MATCH_THRESHOLD = 70;
export const BORDERLINE_MATCH_THRESHOLD = 50;

export function isBorderlineMatch(
  score: number | null | undefined,
  highThreshold: number = HIGH_MATCH_THRESHOLD,
  borderlineThreshold: number = BORDERLINE_MATCH_THRESHOLD,
): boolean {
  if (score === null || score === undefined) return false;
  return score >= borderlineThreshold && score < highThreshold;
}

export function formatMatchScore(score: number | null | undefined): string | null {
  if (score === null || score === undefined) return null;
  return `${score}/100`;
}

export function formatRecommendation(recommendation: string): string {
  return recommendation.replace(/_/g, " ");
}

export const STATUS_LABELS: Record<string, string> = {
  discovered: "Discovered",
  saved: "Saved",
  rejected: "Rejected",
  applied: "Applied",
};

export function materialDisplayContent(material: ApplicationMaterial): string {
  return material.content_preview?.trim() || material.content;
}
