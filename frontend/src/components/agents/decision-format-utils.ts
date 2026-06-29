export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

export function formatEvidenceItem(sectionKey: string, item: unknown): string {
  if (typeof item === "string") return item;
  if (!isRecord(item)) return textValue(item) || "Item available";

  if (sectionKey === "recent_activity") {
    const title = textValue(item.title) || "Activity";
    const description = textValue(item.description);
    return description ? `${title}: ${description}` : title;
  }

  if (sectionKey === "workflow_summaries") {
    const name = textValue(item.name) || "Workflow";
    const status = textValue(item.status);
    const result = isRecord(item.result) ? item.result : {};
    const discovered = textValue(result.discovered_count);
    const evaluated = textValue(result.evaluated_count);
    const topMatch = textValue(result.top_match_score);
    const stats = [
      discovered ? `${discovered} discovered` : "",
      evaluated ? `${evaluated} evaluated` : "",
      topMatch ? `top score ${topMatch}` : "",
    ].filter(Boolean);
    return `${name}${status ? ` (${status})` : ""}${stats.length ? `: ${stats.join(", ")}` : ""}`;
  }

  if (sectionKey === "top_opportunities") {
    const title = textValue(item.title) || "Opportunity";
    const company = textValue(item.company);
    const score = textValue(item.match_score);
    const status = textValue(item.status);
    return `${title}${company ? ` at ${company}` : ""}${score ? ` (${score}/100)` : ""}${status ? ` - ${status}` : ""}`;
  }

  if (sectionKey === "applications") {
    const title = textValue(item.job_title) || "Application";
    const company = textValue(item.job_company);
    const stage = textValue(item.stage);
    return `${title}${company ? ` at ${company}` : ""}${stage ? ` - ${stage}` : ""}`;
  }

  if (sectionKey === "materials") {
    const materialType = textValue(item.material_type) || "Material";
    return `${materialType}${item.opportunity_id ? ` for opportunity ${textValue(item.opportunity_id)}` : ""}`;
  }

  if (sectionKey === "interview_plans") {
    const title = textValue(item.job_title) || "Interview prep";
    return title;
  }

  return Object.entries(item)
    .slice(0, 4)
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${textValue(value) || "available"}`)
    .join("; ");
}

export function formatEvidenceValue(sectionKey: string, value: unknown): string[] {
  if (value === null || value === undefined) return ["None"];
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return ["None"];
    return value.slice(0, 5).map((item) => formatEvidenceItem(sectionKey, item));
  }
  if (isRecord(value)) {
    return Object.entries(value)
      .slice(0, 6)
      .map(([key, entryValue]) => `${key.replace(/_/g, " ")}: ${textValue(entryValue) || "available"}`);
  }
  return ["Evidence available"];
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const STATIC_ROUTES = new Set([
  "/",
  "/opportunities",
  "/applications",
  "/interviews",
  "/resume",
  "/agent-runs",
  "/workspace",
  "/decisions",
  "/companies",
  "/settings",
]);

function looksLikeUuid(value: string): boolean {
  return Boolean(value && UUID_PATTERN.test(value));
}

function workspaceGoalUrl(goal: string): string {
  return `/workspace?goal=${encodeURIComponent(goal)}`;
}

function tailorGoalFromTitle(title: string): string {
  const normalized = title.trim();
  const lowered = normalized.toLowerCase();
  const prefixes = [
    "generate tailored resume for ",
    "tailor resume for ",
    "generate tailored resume ",
  ];
  for (const prefix of prefixes) {
    if (lowered.startsWith(prefix)) {
      const remainder = normalized.slice(prefix.length).trim();
      if (remainder) return `Tailor my resume for ${remainder}`;
    }
  }
  if (lowered.includes("cover letter")) {
    for (const prefix of ["generate cover letter for ", "write cover letter for "]) {
      if (lowered.startsWith(prefix)) {
        const remainder = normalized.slice(prefix.length).trim();
        if (remainder) return `Write a cover letter for ${remainder}`;
      }
    }
    return normalized || "Write a cover letter";
  }
  if (lowered.includes("tailor") && lowered.includes("resume")) {
    return lowered.startsWith("tailor") ? normalized : `Tailor my resume — ${normalized}`;
  }
  return normalized || "Tailor my resume";
}

function isMaterialAction(actionType: string, title: string): boolean {
  if (actionType === "material") return true;
  const lowered = title.toLowerCase();
  return (lowered.includes("tailor") && lowered.includes("resume")) || lowered.includes("cover letter");
}

export interface DecisionActionRouteInput {
  action_type: string;
  target_id?: string;
  title: string;
  route: string;
}

export function resolveDecisionActionRoute(
  action: DecisionActionRouteInput,
  workflowExecutionId?: string | null,
): string {
  const actionType = action.action_type || "profile";
  const targetId = action.target_id?.trim() ?? "";
  const title = action.title?.trim() ?? "";
  let rawRoute = action.route?.trim() || "/";
  if (!rawRoute.startsWith("/")) rawRoute = `/${rawRoute}`;

  const queryIndex = rawRoute.indexOf("?");
  const path = (queryIndex >= 0 ? rawRoute.slice(0, queryIndex) : rawRoute).replace(/\/$/, "") || "/";
  const query = queryIndex >= 0 ? rawRoute.slice(queryIndex + 1) : "";

  const pathParts = path.split("/").filter(Boolean);
  let embeddedId = "";
  if (pathParts.length >= 2 && looksLikeUuid(pathParts[pathParts.length - 1] ?? "")) {
    embeddedId = pathParts[pathParts.length - 1] ?? "";
  }

  const effectiveId = targetId || embeddedId;

  if (isMaterialAction(actionType, title)) {
    return workspaceGoalUrl(tailorGoalFromTitle(title));
  }

  if (actionType === "opportunity" && effectiveId) {
    return `/opportunities?selected=${effectiveId}`;
  }

  if (actionType === "application") {
    return "/applications";
  }

  if (actionType === "interview" && effectiveId) {
    return `/interviews?selected=${effectiveId}&type=prep_plan`;
  }

  const workflowTarget = effectiveId || workflowExecutionId?.trim() || "";
  if (actionType === "workflow" && workflowTarget) {
    return `/workspace?workflow=${workflowTarget}`;
  }

  if (actionType === "agent_run") {
    return "/agent-runs";
  }

  if (actionType === "profile") {
    return "/settings";
  }

  if (STATIC_ROUTES.has(path) && !embeddedId) {
    return query ? `${path}?${query}` : path;
  }

  if (pathParts[0] === "opportunities" && embeddedId) {
    return `/opportunities?selected=${embeddedId}`;
  }

  if ((pathParts[0] === "workspace" || pathParts[0] === "workflows") && embeddedId) {
    return `/workspace?workflow=${embeddedId}`;
  }

  if (query && STATIC_ROUTES.has(path)) {
    return `${path}?${query}`;
  }

  return "/";
}
