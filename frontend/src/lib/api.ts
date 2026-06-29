import { API_URL, AUTH_STORAGE_KEY } from "@/lib/config";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  avatar_url: string;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: User;
}

export interface UserPreferences {
  id: string;
  target_roles: string[];
  target_locations: string[];
  salary_min: number | null;
  salary_max: number | null;
  remote_preference: string;
  career_goals: string;
  skills: string[];
  job_search_schedule_enabled: boolean;
  job_search_schedule_interval_minutes: number | null;
  last_job_search_at: string | null;
  last_scheduled_run_at: string | null;
  next_scheduled_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobScheduleStatus {
  enabled: boolean;
  interval_minutes: number | null;
  last_run_at: string | null;
  next_run_at: string | null;
  last_job_search_at: string | null;
  last_run_summary: string;
}

export interface ResumeAnalysis {
  id: string;
  model_name: string;
  raw_summary: string;
  health_score: number;
  ats_score: number;
  strengths: string[];
  weaknesses: string[];
  missing_keywords: string[];
  improvement_suggestions: string[];
  extracted_skills: string[];
  created_at: string;
}

export interface Resume {
  id: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  extracted_text: string;
  is_active: boolean;
  latest_analysis: ResumeAnalysis | null;
  created_at: string;
  updated_at: string;
  used_fallback?: boolean;
  profile_enriched?: boolean;
  fields_updated?: string[];
}

export interface ActivityEvent {
  id: string;
  event_type: string;
  title: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DashboardNextAction {
  key: string;
  title: string;
  description: string;
  href: string;
}

export interface CompletionSignal {
  key: string;
  label: string;
  weight: number;
}

export interface DashboardSummary {
  profile_completion: number;
  completion_signals: {
    completed: CompletionSignal[];
    missing: CompletionSignal[];
  };
  active_resume: {
    id: string;
    original_filename: string;
    is_active: boolean;
    uploaded_at: string;
    health_score?: number;
    ats_score?: number;
    model_name?: string;
  } | null;
  preferences_summary: {
    target_roles: string[];
    target_locations: string[];
    remote_preference: string;
    skills_count: number;
    has_career_goals: boolean;
  };
  recent_activity: ActivityEvent[];
  next_actions: DashboardNextAction[];
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    let message = "Request failed";
    if (typeof data === "object" && data) {
      if ("detail" in data) {
        message = String((data as { detail: string }).detail);
      } else if ("file" in data) {
        const fileErr = (data as { file: string | string[] }).file;
        message = Array.isArray(fileErr) ? fileErr[0] : String(fileErr);
      }
    }
    throw new ApiError(message, response.status, data);
  }
  return data as T;
}

function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthTokens;
  } catch {
    return null;
  }
}

export function storeAuth(tokens: AuthTokens): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens));
}

export function clearAuth(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function getAuth(): AuthTokens | null {
  return getStoredTokens();
}

let refreshRequest: Promise<AuthTokens> | null = null;

function buildJsonHeaders(options: RequestInit, accessToken?: string | null): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers ?? {}),
  };
  if (accessToken) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${accessToken}`;
  }
  return headers;
}

function buildAuthHeaders(accessToken?: string | null): HeadersInit {
  const headers: HeadersInit = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  return headers;
}

function shouldRefresh(path: string, token?: string | null): boolean {
  if (token) return false;
  if (!path.startsWith("/auth/")) return true;
  return path === "/auth/me/";
}

async function refreshStoredAuth(): Promise<AuthTokens> {
  const stored = getStoredTokens();
  if (!stored?.refresh) {
    throw new ApiError("No refresh token available", 401);
  }

  refreshRequest ??= fetch(`${API_URL}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: stored.refresh }),
  })
    .then((response) => parseResponse<AuthTokens>(response))
    .then((tokens) => {
      storeAuth(tokens);
      return tokens;
    })
    .catch((error) => {
      clearAuth();
      throw error;
    })
    .finally(() => {
      refreshRequest = null;
    });

  return refreshRequest;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const accessToken = token ?? getStoredTokens()?.access;

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: buildJsonHeaders(options, accessToken),
  });

  if (response.status === 401 && shouldRefresh(path, token)) {
    const tokens = await refreshStoredAuth();
    const retryResponse = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: buildJsonHeaders(options, tokens.access),
    });
    return parseResponse<T>(retryResponse);
  }

  return parseResponse<T>(response);
}

export async function apiFetchBlob(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<Blob> {
  const accessToken = token ?? getStoredTokens()?.access;

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: buildAuthHeaders(accessToken),
  });

  if (response.status === 401 && shouldRefresh(path, token)) {
    const tokens = await refreshStoredAuth();
    const retryResponse = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: buildAuthHeaders(tokens.access),
    });
    if (!retryResponse.ok) {
      throw new ApiError("Download failed", retryResponse.status);
    }
    return retryResponse.blob();
  }

  if (!response.ok) {
    throw new ApiError("Download failed", response.status);
  }
  return response.blob();
}

async function apiFetchMultipart<T>(path: string, formData: FormData): Promise<T> {
  const accessToken = getStoredTokens()?.access;

  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: formData,
  });

  if (response.status === 401) {
    const tokens = await refreshStoredAuth();
    const retryResponse = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: buildAuthHeaders(tokens.access),
      body: formData,
    });
    return parseResponse<T>(retryResponse);
  }

  return parseResponse<T>(response);
}

export const authApi = {
  register: (payload: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
  }) =>
    apiFetch<AuthTokens>("/auth/register/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    apiFetch<AuthTokens>("/auth/login/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  google: (payload: { id_token: string }) =>
    apiFetch<AuthTokens>("/auth/google/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  refresh: (refresh: string) =>
    apiFetch<AuthTokens>("/auth/refresh/", {
      method: "POST",
      body: JSON.stringify({ refresh }),
    }),

  me: () => apiFetch<User>("/auth/me/"),
};

export type UserPreferencesUpdate = Partial<
  Omit<
    UserPreferences,
    | "id"
    | "created_at"
    | "updated_at"
    | "last_job_search_at"
    | "last_scheduled_run_at"
    | "next_scheduled_run_at"
  >
>;

export const preferencesApi = {
  get: () => apiFetch<UserPreferences>("/users/preferences/"),

  update: (payload: UserPreferencesUpdate) =>
    apiFetch<UserPreferences>("/users/preferences/", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

export const resumeApi = {
  list: () => apiFetch<Resume[]>("/resumes/"),

  get: (id: string) => apiFetch<Resume>(`/resumes/${id}/`),

  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetchMultipart<Resume>("/resumes/", formData);
  },

  setActive: (id: string) =>
    apiFetch<Resume>(`/resumes/${id}/set-active/`, { method: "POST" }),

  materials: () => apiFetch<ApplicationMaterial[]>("/resumes/materials/"),

  downloadMaterialPdf: (materialId: string) =>
    apiFetchBlob(`/resumes/materials/${materialId}/pdf/`),
};

export const dashboardApi = {
  summary: () => apiFetch<DashboardSummary>("/dashboard/summary/"),
};

export interface WorkflowExecution {
  id: string;
  name: string;
  goal: string;
  status: string;
  context: Record<string, unknown>;
  result: Record<string, unknown>;
  error_message: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListItem extends WorkflowExecution {
  intent?: WorkflowIntent;
  agent_run_count?: number;
  last_agent_at?: string | null;
  planned_agents?: string[];
}

export interface AgentExecution {
  id: string;
  workflow_execution: string | null;
  workflow_goal?: string | null;
  workflow_name?: string | null;
  agent_name: string;
  agent_label?: string;
  status: string;
  input_data?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  reasoning_summary: string;
  error_message: string;
  has_error?: boolean;
  started_at: string | null;
  completed_at: string | null;
  duration_ms?: number | null;
  related_entities?: AgentRelatedEntity[];
  created_at: string;
  updated_at: string;
}

export interface AgentRelatedEntity {
  type: string;
  id: string;
  label: string;
}

export interface PaginatedAgentExecutions {
  count: number;
  limit: number;
  offset: number;
  results: AgentExecution[];
}

export interface AgentExecutionListParams {
  agent_name?: string;
  status?: string;
  workflow_id?: string;
  search?: string;
  offset?: number;
  limit?: number;
}

export interface WorkflowTimelineItem {
  id: string;
  item_type: string;
  timestamp: string;
  title: string;
  description: string;
  workflow_id?: string;
  agent_execution_id?: string;
  agent_name?: string;
  agent_label?: string;
  status?: string;
  duration_ms?: number | null;
  metadata?: Record<string, unknown>;
}

export interface WorkflowTimelineResponse {
  workflow_id: string;
  items: WorkflowTimelineItem[];
}

export interface DecisionAction {
  action_type: string;
  target_id?: string;
  title: string;
  reason: string;
  urgency: "high" | "medium" | "low" | string;
  route: string;
}

export interface DecisionRecommendation {
  id: string;
  workflow_execution: string | null;
  agent_execution_id: string | null;
  status: string;
  summary: string;
  rationale?: string;
  actions: DecisionAction[];
  action_count?: number;
  input_snapshot?: Record<string, unknown>;
  prompt_name?: string;
  prompt_version?: number;
  model_name: string;
  agent_execution?: AgentExecution;
  created_at: string;
  updated_at: string;
}

export interface PaginatedDecisionRecommendations {
  count: number;
  limit: number;
  offset: number;
  results: DecisionRecommendation[];
}

export interface DecisionGenerateResponse {
  recommendation: DecisionRecommendation;
  agent_execution_id: string;
  reasoning_summary: string;
}

export interface WorkflowSuggestedStep {
  key: string;
  title: string;
  description: string;
  phase?: number;
}

export interface ProviderSummaryEntry {
  status: string;
  count?: number;
  companies_enriched?: number;
  configured?: boolean;
  error?: string;
}

export interface ProviderSummary {
  providers: Record<string, ProviderSummaryEntry>;
  errors?: string[];
}

export interface Job {
  id: string;
  external_id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  is_remote: boolean;
  salary_min: string | null;
  salary_max: string | null;
  salary_currency: string;
  description: string;
  apply_url: string;
  posted_at: string | null;
  company_research: {
    available?: boolean;
    summary?: string;
    what_they_do?: string;
    recent_news?: string;
    funding?: string;
    hiring_signals?: string;
    snippets?: Array<{
      title: string;
      url: string;
      snippet: string;
      category?: string;
    }>;
    reason?: string;
  };
  created_at: string;
  updated_at: string;
}

export interface OpportunityEvaluation {
  match_score: number;
  recommendation: string;
  rationale: string;
  strengths: string[];
  gaps: string[];
  factors: Record<
    string,
    { score: number; weight: number; detail: string }
  >;
  agent_execution_id?: string;
}

export interface IntentClassification {
  intent: WorkflowIntent | string;
  method: string;
  matched_phrase?: string | null;
  planned_agents?: string[];
  goal_excerpt?: string;
}

/** Structured constraint extracted by the agentic planner from the user goal. */
export interface PlannerConstraint {
  key: string;
  label?: string;
  value: string;
  source?: string;
}

/** A single tool step in the planner's structured tool plan. */
export interface PlannerToolStep {
  tool: string;
  why: string;
  auto_run?: boolean;
  requires_confirmation?: boolean;
  skipped?: boolean;
  skip_reason?: string;
  params?: Record<string, unknown>;
  status?: "pending" | "running" | "completed" | "skipped" | "failed";
}

/** Success criterion the planner uses to decide when the workflow is done. */
export interface PlannerSuccessCriterion {
  description: string;
  met?: boolean;
}

/** User-facing plan step shown in mission control. */
export interface UserVisiblePlanStep {
  title: string;
  description?: string;
}

/** Record of a replanning decision during agentic execution. */
export interface ReplanEvent {
  at: string;
  action:
    | "continue"
    | "insert_tools"
    | "skip_tool"
    | "ask_user"
    | "complete"
    | "fail_with_reason"
    | string;
  reason: string;
  trigger_tool?: string;
  inserted_tools?: string[];
  skipped_tools?: string[];
}

/** Snapshot of the plan at a point in time (initial plan or after replan). */
export interface PlanHistoryEntry {
  at: string;
  summary: string;
  tool_plan?: PlannerToolStep[];
}

/** Agentic planner fields stored on workflow.result and mirrored on WorkflowDetail. */
export interface AgenticPlannerFields {
  constraints?: PlannerConstraint[];
  tool_plan?: PlannerToolStep[];
  success_criteria?: PlannerSuccessCriterion[];
  user_visible_plan?: UserVisiblePlanStep[] | string;
  plan_history?: PlanHistoryEntry[];
  replan_events?: ReplanEvent[];
  requires_confirmation?: boolean;
  reasoning_summary?: string;
}

export interface ChatRoutingMetadata {
  follow_up_intent: string;
  params?: Record<string, unknown>;
  method: string;
}

export interface ApplicationMaterial {
  id: string;
  opportunity: string;
  opportunity_title: string;
  opportunity_company: string;
  source_resume: string;
  source_resume_filename: string;
  material_type: "tailored_resume" | "cover_letter";
  content: string;
  content_preview?: string;
  prompt_name: string;
  prompt_version: number;
  model_name: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MaterialAgentResponse {
  opportunity: Opportunity;
  material: ApplicationMaterial;
  agent_execution: AgentExecution;
  reasoning_summary: string;
}

export interface OpportunityMaterialsResponse {
  opportunity_id: string;
  materials: ApplicationMaterial[];
}

export interface Opportunity {
  id: string;
  job: Job;
  workflow_execution?: string | null;
  status: string;
  source_agent: string;
  match_context: string;
  match_score: number | null;
  evaluation: OpportunityEvaluation | Record<string, never>;
  created_at: string;
  updated_at?: string;
}

export interface OpportunityListResponse {
  high_match_threshold: number;
  borderline_match_threshold: number;
  pending_evaluation_count: number;
  last_search_summary: LastSearchSummary | null;
  workflow_execution_id?: string | null;
  opportunities: Opportunity[];
}

export interface LastSearchSummary {
  workflow_id: string;
  discovered_count: number;
  evaluated_count: number;
  accepted_count: number;
  borderline_count: number;
  rejected_count: number;
  top_match_score: number;
  high_match_threshold: number;
  borderline_match_threshold: number;
  completed_at: string | null;
}

export interface CompanySummary {
  name: string;
  opportunity_count: number;
  opportunity_ids: string[];
  latest_research: Job["company_research"];
  has_research: boolean;
}

export interface WorkflowStartResponse {
  workflow: WorkflowExecution;
}

export interface WorkflowDetail extends AgenticPlannerFields {
  workflow: WorkflowExecution;
  agent_executions: AgentExecution[];
  workflow_intent?: WorkflowIntent;
  planned_agents?: string[];
  completed_agents?: string[];
  plan_summary: string;
  suggested_steps: WorkflowSuggestedStep[];
  next_action?: string;
  existing_opportunity_count?: number;
  high_match_count?: number;
  saved_count?: number;
  recommended_opportunity_ids?: string[];
  discovered_count: number;
  provider_summary: ProviderSummary;
  job_search_summary: string;
  evaluated_count: number;
  accepted_count: number;
  rejected_count: number;
  top_match_score: number;
  tailor_options?: TailorOptions;
  tailor_selection_pending?: boolean;
  search_rerun_in_progress?: boolean;
  selected_opportunity_id?: string;
  tailored_material_id?: string;
  cover_letter_material_id?: string;
  interview_plan_id?: string;
  interview_prep_target_source?: "application" | "opportunity" | "general";
  tool_progress?: WorkflowToolProgress | null;
}

export interface WorkflowToolProgressEvent {
  kind: "job_evaluation" | "company_research";
  at?: string;
  job_title?: string;
  company?: string;
  match_score?: number;
  recommendation?: string;
  available?: boolean;
  summary?: string;
}

export interface WorkflowToolProgress {
  tool: "job_evaluation" | "company_research";
  status: "running" | "completed";
  current: number;
  total: number;
  current_label?: string;
  recent_events?: WorkflowToolProgressEvent[];
  updated_at?: string;
}

export interface TailorOpportunityOption {
  id: string;
  title: string;
  company: string;
  match_score: number | null;
  status: string;
  location?: string;
  is_remote?: boolean;
}

export interface TailorOptions {
  opportunities: TailorOpportunityOption[];
  supports_custom_jd: boolean;
  keyword_hints?: string[];
}

export interface WorkflowTailorOptionsResponse {
  workflow_id: string;
  goal: string;
  tailor_options: TailorOptions;
  tailor_selection_pending: boolean;
  selected_opportunity_id?: string;
  tailored_material_id?: string;
}

export interface WorkflowTailorResumeResponse {
  workflow: WorkflowExecution;
  opportunity_id: string;
  material: ApplicationMaterial;
  agent_execution: AgentExecution;
  reasoning_summary: string;
  planned_agents: string[];
  completed_agents: string[];
}

export interface WorkflowActionCard {
  key: string;
  label: string;
  description: string;
  params: Record<string, unknown>;
  requires_confirmation: boolean;
  endpoint_hint: string;
  href?: string;
}

export interface WorkflowRefinementResultMetadata {
  kind: "rejected" | "borderline";
  count: number;
  opportunities: Opportunity[];
}

export interface WorkflowMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  actions: WorkflowActionCard[];
  metadata?: {
    routing?: ChatRoutingMetadata;
    refinement_result?: WorkflowRefinementResultMetadata;
    tailor_selection?: {
      pending?: boolean;
      tailor_options?: TailorOptions;
    };
    [key: string]: unknown;
  };
  created_at: string;
}

export interface WorkflowMessagesResponse {
  workflow_id: string;
  messages: WorkflowMessage[];
}

export interface WorkflowPostMessageResponse {
  user_message: WorkflowMessage;
  assistant_message: WorkflowMessage;
  actions: WorkflowActionCard[];
  confirmed?: boolean;
  system_message?: WorkflowMessage;
  results?: Record<string, unknown>[];
  workflow?: WorkflowExecution;
}

export interface WorkflowActionResponse {
  action_key: string;
  result: Record<string, unknown>;
  system_message: WorkflowMessage;
  assistant_message: WorkflowMessage;
  workflow: WorkflowExecution;
}

export type WorkflowIntent =
  | "job_discovery"
  | "tailor_resume"
  | "cover_letter"
  | "interview_prep"
  | "application_tracking";

/** @deprecated Use WorkflowDetail after polling; kept for rerun responses */
export interface WorkflowStartResult {
  workflow: WorkflowExecution;
  planner_execution: AgentExecution;
  job_search_execution: AgentExecution;
  plan_summary: string;
  suggested_steps: WorkflowSuggestedStep[];
  discovered_count: number;
  provider_summary: ProviderSummary;
  job_search_summary: string;
  evaluated_count?: number;
  top_match_score?: number;
  evaluation_executions?: AgentExecution[];
}

export const workflowApi = {
  list: () => apiFetch<WorkflowListItem[]>("/workflows/"),

  start: (goal: string) =>
    apiFetch<WorkflowStartResponse>("/workflows/", {
      method: "POST",
      body: JSON.stringify({ goal }),
    }),

  get: (workflowId: string) =>
    apiFetch<WorkflowDetail>(`/workflows/${workflowId}/`),

  rerunJobSearch: (workflowId: string) =>
    apiFetch<{
      workflow: WorkflowExecution;
      job_search_execution: AgentExecution;
      discovered_count: number;
      provider_summary: ProviderSummary;
      job_search_summary: string;
    }>(`/workflows/${workflowId}/job-search/`, { method: "POST" }),

  timeline: (workflowId: string) =>
    apiFetch<WorkflowTimelineResponse>(`/workflows/${workflowId}/timeline/`),

  tailorOptions: (workflowId: string) =>
    apiFetch<WorkflowTailorOptionsResponse>(`/workflows/${workflowId}/tailor-options/`),

  tailorResume: (
    workflowId: string,
    body:
      | { opportunity_id: string }
      | { title: string; company?: string; job_description: string },
  ) =>
    apiFetch<WorkflowTailorResumeResponse>(`/workflows/${workflowId}/tailor-resume/`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  messages: (workflowId: string) =>
    apiFetch<WorkflowMessagesResponse>(`/workflows/${workflowId}/messages/`),

  postMessage: (workflowId: string, content: string) =>
    apiFetch<WorkflowPostMessageResponse>(`/workflows/${workflowId}/messages/`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  executeAction: (
    workflowId: string,
    body: { action_key: string; params?: Record<string, unknown>; confirmed: boolean },
  ) =>
    apiFetch<WorkflowActionResponse>(`/workflows/${workflowId}/actions/`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export const opportunitiesApi = {
  scheduleStatus: () => apiFetch<JobScheduleStatus>("/opportunities/schedule-status/"),

  list: (params?: {
    include_rejected?: boolean;
    include_low_match?: boolean;
    workflow_id?: string;
    filter?: "high_match" | "borderline" | "rejected" | "all";
  }) => {
    const search = new URLSearchParams();
    if (params?.include_rejected) search.set("include_rejected", "true");
    if (params?.include_low_match) search.set("include_low_match", "true");
    if (params?.workflow_id) search.set("workflow_id", params.workflow_id);
    if (params?.filter) search.set("filter", params.filter);
    const query = search.toString();
    return apiFetch<OpportunityListResponse>(
      `/opportunities${query ? `?${query}` : ""}`,
    );
  },

  detail: (id: string) => apiFetch<Opportunity>(`/opportunities/${id}/`),

  updateStatus: (id: string, status: string) =>
    apiFetch<Opportunity>(`/opportunities/${id}/`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  researchCompany: (id: string) =>
    apiFetch<{
      opportunity: Opportunity;
      company_research: Job["company_research"];
      agent_execution: AgentExecution;
      reasoning_summary: string;
    }>(`/opportunities/${id}/research-company/`, { method: "POST" }),

  evaluate: (id: string) =>
    apiFetch<{
      opportunity: Opportunity;
      match_score: number;
      evaluation: OpportunityEvaluation;
      agent_execution: AgentExecution;
      reasoning_summary: string;
    }>(`/opportunities/${id}/evaluate/`, { method: "POST" }),

  tailorResume: (id: string) =>
    apiFetch<MaterialAgentResponse>(
      `/opportunities/${id}/tailor-resume/`,
      { method: "POST" },
    ),

  generateCoverLetter: (id: string) =>
    apiFetch<MaterialAgentResponse>(
      `/opportunities/${id}/cover-letter/`,
      { method: "POST" },
    ),

  materials: (id: string) =>
    apiFetch<OpportunityMaterialsResponse>(
      `/opportunities/${id}/materials/`,
    ),

  generateInterviewPrep: (id: string) =>
    apiFetch<InterviewPrepAgentResponse>(
      `/opportunities/${id}/interview-prep/`,
      { method: "POST" },
    ),
};

export const companiesApi = {
  list: () => apiFetch<CompanySummary[]>("/companies/"),
};

export interface ApplicationStageEvent {
  id: string;
  from_stage: string;
  to_stage: string;
  notes: string;
  created_at: string;
}

export interface Application {
  id: string;
  opportunity: Opportunity;
  job_title: string;
  job_company: string;
  match_score: number | null;
  stage: string;
  applied_at: string | null;
  target_follow_up_at: string | null;
  notes: string;
  priority: string;
  has_tailored_resume: boolean;
  has_cover_letter: boolean;
  created_at: string;
  updated_at: string;
  job?: Job;
  stage_events?: ApplicationStageEvent[];
  materials?: ApplicationMaterial[];
  interview_plans?: InterviewPlanSummary[];
}

export interface ApplicationKanbanResponse {
  stage_order: string[];
  stages: Record<string, Application[]>;
}

export type ApplicationDetailResponse = Application;

export interface CreateApplicationResponse {
  application: ApplicationDetailResponse;
  created: boolean;
}

export interface InterviewPlanContent {
  prep_roadmap?: string[];
  likely_questions?: string[];
  system_design_topics?: string[];
  company_talking_points?: string[];
  resume_stories?: string[];
  gaps_to_practice?: string[];
  day_by_day_checklist?: Array<{ day: number; tasks: string[] }>;
}

export interface InterviewPlanSummary {
  id: string;
  type: "prep_plan";
  opportunity_id: string;
  application_id: string | null;
  interview_id?: string | null;
  job_title: string;
  job_company: string;
  application_stage: string | null;
  prompt_name: string;
  prompt_version: number;
  model_name: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ScheduledInterviewSummary {
  id: string;
  type: "scheduled";
  opportunity_id: string;
  application_id: string | null;
  job_title: string;
  job_company: string;
  scheduled_at: string | null;
  round_label: string;
  format: string;
  outcome: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export type InterviewListItem = InterviewPlanSummary | ScheduledInterviewSummary;

export interface ScheduledInterview extends ScheduledInterviewSummary {
  interviewer_notes: string;
  job_description: string;
}

export interface InterviewListResponse {
  upcoming_interviews: ScheduledInterviewSummary[];
  active: InterviewPlanSummary[];
  upcoming: InterviewPlanSummary[];
  recent: InterviewPlanSummary[];
}

export interface CreateInterviewPayload {
  company: string;
  job_title: string;
  scheduled_at?: string | null;
  round_label?: string;
  format?: string;
  interviewer_notes?: string;
  outcome?: string;
  job_description?: string;
}

export interface UpdateInterviewPayload {
  scheduled_at?: string | null;
  round_label?: string;
  format?: string;
  interviewer_notes?: string;
  outcome?: string;
  job_description?: string;
}

export interface InterviewPlan extends InterviewPlanSummary {
  content: InterviewPlanContent;
  markdown: string;
  reasoning_summary: string;
}

export type InterviewDetail = InterviewPlan | ScheduledInterview;

export interface InterviewPrepAgentResponse {
  opportunity?: Opportunity;
  application?: Application;
  interview_plan: InterviewPlan;
  agent_execution: AgentExecution;
  reasoning_summary: string;
}

export const applicationsApi = {
  list: () => apiFetch<ApplicationKanbanResponse>("/applications/"),

  forOpportunity: (opportunityId: string) =>
    apiFetch<{ application: Application | null }>(
      `/applications/for-opportunity/${opportunityId}/`,
    ),

  createFromOpportunity: (opportunityId: string) =>
    apiFetch<CreateApplicationResponse>(
      `/applications/from-opportunity/${opportunityId}/`,
      { method: "POST" },
    ),

  detail: (id: string) => apiFetch<ApplicationDetailResponse>(`/applications/${id}/`),

  update: (
    id: string,
    payload: Partial<{
      stage: string;
      notes: string;
      priority: string;
      target_follow_up_at: string | null;
      stage_notes: string;
    }>,
  ) =>
    apiFetch<ApplicationDetailResponse>(`/applications/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  generateInterviewPrep: (id: string) =>
    apiFetch<InterviewPrepAgentResponse>(
      `/applications/${id}/interview-prep/`,
      { method: "POST" },
    ),
};

export const interviewsApi = {
  list: () => apiFetch<InterviewListResponse>("/interviews/"),

  create: (payload: CreateInterviewPayload) =>
    apiFetch<ScheduledInterview>("/interviews/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  detail: (id: string) => apiFetch<InterviewDetail>(`/interviews/${id}/`),

  update: (id: string, payload: UpdateInterviewPayload) =>
    apiFetch<ScheduledInterview>(`/interviews/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  generateInterviewPrep: (id: string) =>
    apiFetch<InterviewPrepAgentResponse & { interview?: ScheduledInterview }>(
      `/interviews/${id}/interview-prep/`,
      { method: "POST" },
    ),
};

export const agentsApi = {
  listExecutions: (params?: AgentExecutionListParams) => {
    const search = new URLSearchParams();
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.status) search.set("status", params.status);
    if (params?.workflow_id) search.set("workflow_id", params.workflow_id);
    if (params?.search) search.set("search", params.search);
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiFetch<PaginatedAgentExecutions>(
      `/agents/executions/${query ? `?${query}` : ""}`,
    );
  },

  detail: (id: string) => apiFetch<AgentExecution>(`/agents/executions/${id}/`),
};

export const decisionsApi = {
  generate: (payload?: { workflow_id?: string }) =>
    apiFetch<DecisionGenerateResponse>("/decisions/", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),

  list: (params?: { workflow_id?: string; offset?: number; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.workflow_id) search.set("workflow_id", params.workflow_id);
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiFetch<PaginatedDecisionRecommendations>(
      `/decisions/${query ? `?${query}` : ""}`,
    );
  },

  latest: () => apiFetch<DecisionRecommendation>("/decisions/latest/"),

  detail: (id: string) => apiFetch<DecisionRecommendation>(`/decisions/${id}/`),
};

export const healthApi = {
  check: () =>
    apiFetch<{ status: string; database: string }>("/health/"),
};
