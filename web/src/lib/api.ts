export const API_BASE = import.meta.env.VITE_API_URL || "";

export type ProtocolRecommendation = {
  key: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  action_items: string[];
  nutrition_focus: string[];
  recheck_interval: string;
  templates: Array<{ key: string; title: string; summary: string }>;
  source: string;
};

export type AssessmentResult = {
  assessment_id?: string | null;
  triggered: Array<{
    title: string;
    category: string;
    priority: string;
    action_items: string[];
    sex_group: string;
    age_group: string;
  }>;
  ratings: Array<{
    parameter: string;
    value: number | null;
    rating: string;
    unit: string;
  }>;
  training_zones: {
    source: string;
    hr_max: number;
    vt1_bpm: number;
    vt2_bpm: number;
    zones: Record<string, string>;
  } | null;
  protocol_recommendations?: ProtocolRecommendation[];
  context_for_llm: string;
  member_summary: string;
  sex_group: string;
  age_group: string;
};

import type { AppUser, PersonalProfile } from "./profileFields";

const expertTokenKey = "ayun_expert_token";
const expertNameKey = "ayun_expert_name";
const memberTokenKey = "ayun_member_token";
const memberEmailKey = "ayun_member_email";
const activeModeKey = "ayun_active_mode";
const assessmentIdKey = "ayun_assessment_id";
const guestTicketIdsKey = "ayun_guest_ticket_ids";

export function getStoredAssessmentId(): string | null {
  return localStorage.getItem(assessmentIdKey);
}

export function setStoredAssessmentId(id: string | null) {
  if (id) localStorage.setItem(assessmentIdKey, id);
  else localStorage.removeItem(assessmentIdKey);
}

export function getGuestTicketIds(): string[] {
  try {
    const raw = localStorage.getItem(guestTicketIdsKey);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function addGuestTicketId(id: string) {
  const ids = getGuestTicketIds();
  if (!ids.includes(id)) {
    localStorage.setItem(guestTicketIdsKey, JSON.stringify([...ids, id]));
  }
}

export function clearGuestTicketIds() {
  localStorage.removeItem(guestTicketIdsKey);
}

export type AuthMode = false | "member" | "expert" | "optionalMember";
export type ActiveMode = "member" | "expert";

export function getExpertToken(): string | null {
  return localStorage.getItem(expertTokenKey);
}

export function setExpertSession(token: string, name: string) {
  localStorage.setItem(expertTokenKey, token);
  localStorage.setItem(expertNameKey, name);
}

export function clearExpertSession() {
  localStorage.removeItem(expertTokenKey);
  localStorage.removeItem(expertNameKey);
}

export function getExpertName(): string | null {
  return localStorage.getItem(expertNameKey);
}

export function getMemberToken(): string | null {
  return localStorage.getItem(memberTokenKey);
}

export function setMemberSession(token: string, email: string) {
  localStorage.setItem(memberTokenKey, token);
  localStorage.setItem(memberEmailKey, email);
}

export function clearMemberSession() {
  localStorage.removeItem(memberTokenKey);
  localStorage.removeItem(memberEmailKey);
}

export function getMemberEmail(): string | null {
  return localStorage.getItem(memberEmailKey);
}

export function getStoredActiveMode(): ActiveMode {
  const mode = localStorage.getItem(activeModeKey);
  return mode === "expert" ? "expert" : "member";
}

export function setStoredActiveMode(mode: ActiveMode) {
  localStorage.setItem(activeModeKey, mode);
}

/** Hide provider payloads. Members should see a sentence, not an error dump. */
export function calmAiMessage(detail: string): string {
  const text = detail.trim();
  const lower = text.toLowerCase();
  const technical =
    lower.includes("ai request failed") ||
    lower.includes("error code") ||
    lower.includes("{") ||
    lower.includes("[");
  const busy =
    lower.includes("high demand") ||
    lower.includes("unavailable") ||
    lower.includes("overloaded") ||
    lower.includes("rate limit") ||
    lower.includes("too many requests") ||
    lower.includes("try again later");
  if (busy) return "Joule is busy right now. Please try again in a moment.";
  if (technical) return "Joule couldn't answer just now. Please try again.";
  return text;
}

function parseApiError(res: Response, body: unknown): string {
  let detail = "";
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") detail = d;
    else if (Array.isArray(d)) {
      detail = d
        .map((item) =>
          typeof item === "object" && item && "msg" in item ? String((item as { msg: string }).msg) : String(item),
        )
        .join("; ");
    }
  }
  if (detail) return calmAiMessage(detail);
  if (res.status >= 500) {
    return "Server error — redeploy latest main or check host environment variables.";
  }
  return res.statusText || "Request failed";
}

async function apiFetch<T>(path: string, options: RequestInit & { auth?: AuthMode } = {}): Promise<T> {
  const authMode = options.auth ?? false;
  let token: string | null = null;
  if (authMode === "member") token = getMemberToken();
  else if (authMode === "expert") token = getExpertToken();
  else if (authMode === "optionalMember") token = getMemberToken();

  const { auth: _auth, ...fetchOptions } = options;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(fetchOptions.headers || {}),
      },
    });
  } catch {
    throw new Error("Cannot reach API — run: uvicorn api.main:app --reload --port 8000");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(parseApiError(res, err));
  }
  return res.json();
}

export async function fetchLatestAssessment() {
  return apiFetch<{ assessment: AssessmentResult | null }>("/api/assessments/latest", {
    auth: "member",
  });
}

export async function createAssessment(
  memberData: Record<string, unknown>,
  pseudonym = "",
  personalProfile?: PersonalProfile | null,
) {
  return apiFetch<AssessmentResult>("/api/assessments", {
    method: "POST",
    auth: "member",
    body: JSON.stringify({
      member_data: memberData,
      pseudonym,
      personal_profile: personalProfile ?? undefined,
    }),
  });
}

export type ReviewRecommendation = {
  id: string;
  title: string;
  category: string;
  original_priority?: string;
  reviewed_priority: string;
  action_items: string[] | string;
  clinician_notes?: string;
  source?: string;
  removed?: boolean;
};

export type SavedAssessmentSummary = {
  id: string;
  member_user_id?: string | null;
  member_name: string;
  pseudonym: string;
  created_at: string;
  has_published_plan: boolean;
  published_at?: string;
  published_by?: string;
  triggered_count: number;
  draft_count: number;
};

export type SavedAssessmentDetail = SavedAssessmentSummary & {
  assessment: AssessmentResult;
  draft_recommendations: ReviewRecommendation[];
  personal_profile: import("./profileFields").PersonalProfile;
  member_data: Record<string, unknown>;
  published: {
    recommendations: ReviewRecommendation[];
    published_by: string;
    published_at: string;
    clinician_note?: string;
  } | null;
};

export type MemberDirectoryAssessment = {
  id: string;
  created_at: string;
  has_published_plan: boolean;
  triggered_count: number;
  archived_from_inbox: boolean;
};

export type MemberDirectoryEntry = {
  member_key: string;
  member_user_id?: string | null;
  member_name: string;
  pseudonym: string;
  email?: string;
  personal_profile: import("./profileFields").PersonalProfile;
  member_data: Record<string, unknown>;
  assessment_count: number;
  latest_assessment_id: string;
  latest_created_at: string;
  has_published_plan: boolean;
  assessments: MemberDirectoryAssessment[];
};

export type PublishedPlan = {
  assessment_id: string;
  member_name?: string;
  recommendations: ReviewRecommendation[];
  removed_titles?: string[];
  published_by: string;
  published_at: string;
  clinician_note?: string;
};

export async function fetchReviewAssessments(status: "pending" | "published" | "all" = "pending") {
  return apiFetch<{ assessments: SavedAssessmentSummary[] }>(
    `/api/reviews/assessments?status=${status}`,
    { auth: "expert" },
  );
}

export async function fetchMemberDirectory() {
  return apiFetch<{ members: MemberDirectoryEntry[] }>("/api/reviews/members", { auth: "expert" });
}

export async function fetchMemberDirectoryEntry(memberKey: string) {
  return apiFetch<MemberDirectoryEntry>(
    `/api/reviews/members/${encodeURIComponent(memberKey)}`,
    { auth: "expert" },
  );
}

export async function archiveReviewAssessment(id: string) {
  return apiFetch<{ ok: boolean; id: string }>(`/api/reviews/assessments/${id}`, {
    method: "DELETE",
    auth: "expert",
  });
}

export async function fetchReviewAssessment(id: string) {
  return apiFetch<SavedAssessmentDetail>(`/api/reviews/assessments/${id}`, { auth: "expert" });
}

export async function updateReviewAssessmentContext(
  assessmentId: string,
  payload: {
    member_name?: string;
    personal_profile?: import("./profileFields").PersonalProfile;
    member_data?: Record<string, unknown>;
  },
) {
  return apiFetch<SavedAssessmentDetail>(`/api/reviews/assessments/${assessmentId}/context`, {
    method: "PUT",
    auth: "expert",
    body: JSON.stringify(payload),
  });
}

export async function updateMemberDirectoryContext(
  memberKey: string,
  payload: {
    member_name?: string;
    personal_profile?: import("./profileFields").PersonalProfile;
    member_data?: Record<string, unknown>;
  },
) {
  return apiFetch<MemberDirectoryEntry>(
    `/api/reviews/members/${encodeURIComponent(memberKey)}/context`,
    {
      method: "PUT",
      auth: "expert",
      body: JSON.stringify(payload),
    },
  );
}

export async function saveReviewDraft(id: string, recommendations: ReviewRecommendation[]) {
  return apiFetch<SavedAssessmentDetail>(`/api/reviews/assessments/${id}/draft`, {
    method: "PUT",
    auth: "expert",
    body: JSON.stringify({ recommendations }),
  });
}

export async function publishReviewPlan(
  id: string,
  recommendations: ReviewRecommendation[],
  clinicianNote = "",
) {
  return apiFetch<SavedAssessmentDetail>(`/api/reviews/assessments/${id}/publish`, {
    method: "POST",
    auth: "expert",
    body: JSON.stringify({ recommendations, clinician_note: clinicianNote }),
  });
}

export async function fetchPublishedPlan(options?: { assessmentId?: string | null; asMember?: boolean }) {
  const assessmentId = options?.assessmentId;
  const q = assessmentId ? `?assessment_id=${encodeURIComponent(assessmentId)}` : "";
  return apiFetch<{ published: PublishedPlan | null }>(`/api/plan/published${q}`, {
    auth: options?.asMember ? "member" : false,
  });
}

export async function downloadProtocolPdf(options: {
  path: string;
  auth: "member" | "expert";
  body?: unknown;
  fallbackName?: string;
}) {
  const token = options.auth === "expert" ? getExpertToken() : getMemberToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${options.path}`, {
      method: options.body === undefined ? "GET" : "POST",
      headers: {
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new Error("Cannot reach API — run: uvicorn api.main:app --reload --port 8000");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(parseApiError(res, err));
  }
  const blob = await res.blob();
  const match = /filename="?([^";]+)"?/i.exec(res.headers.get("Content-Disposition") || "");
  const name = match?.[1] || options.fallbackName || "AYUN-sports-performance.pdf";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function memberRegister(email: string, password: string, displayName = "") {
  return apiFetch<{ token: string; user: AppUser }>("/api/auth/member/register", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export async function memberLogin(email: string, password: string) {
  return apiFetch<{ token: string; user: AppUser }>("/api/auth/member/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchGoogleAuthStatus() {
  const origin = encodeURIComponent(window.location.origin);
  return apiFetch<{ googleEnabled: boolean; javascriptOrigin: string; redirectUri: string }>(
    `/api/auth/member/google/status?origin=${origin}`,
    { auth: false },
  );
}

export async function startGoogleSignIn() {
  return apiFetch<{ url: string; redirectUri: string }>("/api/auth/member/google", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ origin: window.location.origin }),
  });
}

export async function exchangeGoogleSignIn(code: string, state: string) {
  return apiFetch<{ token: string; user: AppUser }>("/api/auth/member/google/exchange", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ code, state }),
  });
}

export async function memberLogout() {
  return apiFetch<{ ok: boolean }>("/api/auth/member/logout", {
    method: "POST",
    auth: "member",
  });
}

export async function fetchMemberMe() {
  return apiFetch<AppUser>("/api/auth/member/me", { auth: "member" });
}

export async function updateMemberProfile(payload: {
  display_name?: string;
  pseudonym?: string;
  member_data?: Record<string, unknown>;
  personal_profile?: PersonalProfile;
  enabled_sections?: Record<string, boolean>;
}) {
  return apiFetch<AppUser>("/api/auth/member/profile", {
    method: "PUT",
    auth: "member",
    body: JSON.stringify(payload),
  });
}

export async function expertLogin(name: string, password: string) {
  return apiFetch<{ token: string; name: string; role: string }>("/api/auth/expert/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ name, password }),
  });
}

export async function expertLogout() {
  return apiFetch<{ ok: boolean }>("/api/auth/expert/logout", {
    method: "POST",
    auth: "expert",
  });
}

export async function fetchExpertMe() {
  return apiFetch<{ name: string; role: string; expert_id: string }>("/api/auth/expert/me", {
    auth: "expert",
  });
}

export async function fetchExpertStatus() {
  return apiFetch<{ configured: boolean }>("/api/auth/expert/status", { auth: false });
}

export async function fetchHealth() {
  return apiFetch<{ status: string; elevenlabs?: boolean }>("/api/health", { auth: false });
}

export type JouleVoice = {
  id: string;
  name: string;
  vibe: string;
  lang?: string;
  greeting?: string;
};

export async function fetchJouleVoices() {
  return apiFetch<{
    configured: boolean;
    model: string | null;
    default_voice_id: string;
    hint: string | null;
    voices: JouleVoice[];
  }>("/api/voice/voices", { auth: false });
}

export async function speakElevenLabs(text: string, voiceId: string, signal?: AbortSignal) {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice_id: voiceId }),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new Error("Cannot reach API — run: uvicorn api.main:app --reload --port 8000");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(parseApiError(res, err));
  }
  const buffer = await res.arrayBuffer();
  return new Blob([buffer], { type: "audio/mpeg" });
}

export async function fetchKnowledgeStats() {
  return apiFetch<{
    backend: string;
    nodes: number;
    tickets_open: number;
    tickets_answered: number;
    tickets_validated: number;
    tickets_total?: number;
  }>("/api/knowledge/stats", { auth: "expert" });
}

export async function fetchTickets(status?: string) {
  const q = status ? `?status=${status}` : "";
  return apiFetch<{ tickets: Ticket[]; expert_id?: string }>(`/api/tickets${q}`, { auth: "expert" });
}

export async function fetchMyTickets() {
  return apiFetch<{ tickets: Ticket[] }>("/api/tickets/mine", { auth: "member" });
}

export async function claimMemberTickets(ticketIds: string[]) {
  return apiFetch<{ claimed: number; tickets: Ticket[] }>("/api/tickets/claim", {
    method: "POST",
    auth: "member",
    body: JSON.stringify({ ticket_ids: ticketIds }),
  });
}

export async function fetchGuestTickets(ticketIds: string[]) {
  return apiFetch<{ tickets: Ticket[] }>("/api/tickets/guest", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ ticket_ids: ticketIds }),
  });
}

export async function fetchExperts() {
  return apiFetch<{ experts: Expert[] }>("/api/experts", { auth: false });
}

export async function createTicket(payload: {
  question: string;
  from_name: string;
  category: string;
  assigned_expert_id: string;
  source?: string;
  member_snapshot?: Record<string, unknown> | null;
  chat_context?: string;
}) {
  return apiFetch<Ticket>("/api/tickets", {
    method: "POST",
    auth: "member",
    body: JSON.stringify({
      ...payload,
      from_role: "patient",
      source: payload.source || "patient_direct",
    }),
  });
}

export async function deleteTicket(id: string) {
  return apiFetch<{ ok: boolean; id: string }>(`/api/tickets/${id}`, {
    method: "DELETE",
    auth: "expert",
  });
}

export type TicketDetail = Ticket & {
  member_snapshot?: Record<string, unknown>;
  chat_context?: string;
  member_user_id?: string | null;
  assigned_expert_name?: string;
  member_context_text?: string;
  personal_profile?: import("./profileFields").PersonalProfile;
  member_data?: Record<string, unknown>;
  email?: string;
  pseudonym?: string;
  member_name?: string;
  has_directory_profile?: boolean;
  evipedia_matches?: EvipediaReference[];
  evipedia_match_mode?: string;
};

export async function fetchTicketDetail(id: string) {
  return apiFetch<TicketDetail>(`/api/tickets/${id}`, { auth: "expert" });
}

export async function expertTicketAssistChat(id: string, messages: Array<{ role: string; content: string }>) {
  return apiFetch<{ reply: string; citations?: import("./sources").AnswerCitation[] }>(`/api/tickets/${id}/assist/chat`, {
    method: "POST",
    auth: "expert",
    body: JSON.stringify({ messages }),
  });
}

export async function expertTicketPolishAnswer(id: string, draftAnswer: string) {
  return apiFetch<{ polished: string }>(`/api/tickets/${id}/assist/polish`, {
    method: "POST",
    auth: "expert",
    body: JSON.stringify({ draft_answer: draftAnswer }),
  });
}

export async function expertTicketSuggestDraft(id: string) {
  return apiFetch<{ suggestion: string }>(`/api/tickets/${id}/assist/suggest`, {
    method: "POST",
    auth: "expert",
  });
}

export async function updateTicket(id: string, draft_answer: string, action: "save_draft" | "validate") {
  return apiFetch<Ticket>(`/api/tickets/${id}`, {
    method: "PATCH",
    auth: "expert",
    body: JSON.stringify({ draft_answer, action }),
  });
}

export type SavedAskExchange = {
  id: string;
  question: string;
  answer: string;
  mode: "cited" | "talk" | string;
  citations: import("./sources").AnswerCitation[];
  confidence: string;
  created_at: string;
};

export async function fetchAskHistory() {
  return apiFetch<{ exchanges: SavedAskExchange[] }>("/api/chat/history", { auth: "member" });
}

export async function saveAskExchange(payload: {
  question: string;
  answer: string;
  mode?: string;
  citations?: import("./sources").AnswerCitation[];
  confidence?: string;
}) {
  return apiFetch<{ exchange: SavedAskExchange }>("/api/chat/history", {
    method: "POST",
    auth: "member",
    body: JSON.stringify(payload),
  });
}

export async function clearAskHistory() {
  return apiFetch<{ ok: boolean; deleted: number }>("/api/chat/history", {
    method: "DELETE",
    auth: "member",
  });
}

export async function fetchChatStatus() {
  return apiFetch<{
    configured: boolean;
    model: string;
    provider?: string;
    hint?: string;
  }>("/api/chat/status", { auth: false });
}

export async function chatAsk(
  question: string,
  context: string,
  fromName: string,
  memberSnapshot?: Record<string, unknown> | null,
) {
  return apiFetch<{
    error?: string;
    answer: string;
    confidence: string;
    citations: Array<{
      index?: string;
      marker?: string;
      title: string;
      family?: "protocol" | "member" | "web";
      kind?: string;
      excerpt?: string;
      locator?: string;
      url?: string;
      origin?: string;
      used?: boolean | string;
      protocol?: ProtocolRecommendation | null;
    }>;
    ticket_id?: string | null;
  }>("/api/chat/ask", {
    method: "POST",
    auth: "member",
    body: JSON.stringify({
      question,
      context,
      from_name: fromName,
      from_role: "patient",
      auto_ticket: false,
      member_snapshot: memberSnapshot ?? null,
    }),
  });
}

export async function chatMessage(messages: Array<{ role: string; content: string }>, context: string) {
  return apiFetch<{ reply: string; error?: string }>("/api/chat", {
    method: "POST",
    auth: "member",
    body: JSON.stringify({ messages, context }),
  });
}

export function peelTalkTicket(text: string): {
  reply: string;
  ticketId: string;
  proposedQuestion: string;
} {
  let ticketId = "";
  let proposedQuestion = "";
  const reply = (text || "")
    .replace(/<!--ayun-ticket-propose:([^>]+)-->/gi, (_, raw: string) => {
      try {
        proposedQuestion = decodeURIComponent(String(raw || "").trim());
      } catch {
        proposedQuestion = String(raw || "").trim();
      }
      return "";
    })
    .replace(/<!--ayun-ticket:([^>]+)-->/gi, (_, id: string) => {
      ticketId = String(id || "").trim();
      return "";
    })
    .replace(/^\s*TICKET:\s*.+$/gim, "")
    .trim();
  return { reply, ticketId, proposedQuestion };
}

export async function chatMessageStream(
  messages: Array<{ role: string; content: string }>,
  context: string,
  onChunk: (text: string) => void,
  language = "en",
  extras?: { fromName?: string; memberSnapshot?: Record<string, unknown> | null },
): Promise<{ reply: string; ticketId: string; proposedQuestion: string }> {
  const token = getMemberToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        messages,
        context,
        spoken: true,
        language,
        from_name: extras?.fromName || "Member",
        member_snapshot: extras?.memberSnapshot ?? null,
      }),
    });
  } catch {
    throw new Error("Cannot reach API — run: uvicorn api.main:app --reload --port 8000");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(parseApiError(res, err));
  }
  if (!res.body) throw new Error("Joule couldn't answer just now. Please try again.");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let full = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    full += decoder.decode(value, { stream: true });
    onChunk(peelTalkTicket(full).reply);
  }
  const peeled = peelTalkTicket(full);
  onChunk(peeled.reply);
  if (peeled.ticketId && !getMemberToken()) addGuestTicketId(peeled.ticketId);
  return peeled;
}

export async function fetchKnowledgeNodes() {
  return apiFetch<{ nodes: KnowledgeNode[] }>("/api/knowledge/nodes", { auth: "expert" });
}

export async function fetchKnowledgeValidatedQa() {
  return apiFetch<{ tickets: Ticket[] }>("/api/knowledge/qa", { auth: "expert" });
}

export type KnowledgeSearchHit = {
  id: string;
  kind: "node" | "qa" | "evipedia" | "protocol";
  title: string;
  snippet: string;
  category: string;
  score: number;
  source: string;
  created_at: string;
  captured_by?: string;
  validated_by?: string;
  from_name?: string;
  url?: string;
  slug?: string;
  tags?: string[];
  match_mode?: string;
};

export type KnowledgeProtocol = {
  key: string;
  kind: "condition_protocol" | "training_template";
  title: string;
  description: string;
  training: Record<string, string | string[]>;
  nutrition_focus?: string[];
  exercises?: string[];
  structure?: string[];
  zones?: string[];
  tips?: string[];
  modalities?: string[];
  evidence?: string[];
  recheck_interval?: string;
  related_templates: Array<{
    key: string;
    title: string;
    description?: string;
    frequency?: string;
    intensity?: string;
    duration?: string;
    exercises?: string[];
    structure?: string[];
    zones?: string[];
    tips?: string[];
    modalities?: string[];
  }>;
  source: string;
};

export type EvipediaReference = {
  id: string;
  title: string;
  slug: string;
  url: string;
  category: string;
  summary: string;
  tags: string[];
  ayun_topics: string[];
  score?: number;
  kind?: string;
  snippet?: string;
  source?: string;
  match_mode?: string;
};

export async function fetchKnowledgeSearch(query: string, limit = 20) {
  const q = encodeURIComponent(query.trim());
  return apiFetch<{
    query: string;
    mode: string;
    total: number;
    results: KnowledgeSearchHit[];
  }>(`/api/knowledge/search?q=${q}&limit=${limit}`, { auth: "expert" });
}

export async function fetchKnowledgeProtocols() {
  return apiFetch<{ source: string; protocols: KnowledgeProtocol[]; total: number }>(
    "/api/knowledge/protocols",
    { auth: "expert" },
  );
}

export async function fetchEvipediaCatalog(category = "") {
  const q = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch<{ source: string; references: EvipediaReference[] }>(
    `/api/knowledge/evipedia${q}`,
    { auth: "expert" },
  );
}

export async function fetchEvipediaMatch(query: string, category = "", limit = 6) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (category.trim()) params.set("category", category.trim());
  params.set("limit", String(limit));
  return apiFetch<{ query: string; category: string; mode: string; matches: EvipediaReference[]; total: number }>(
    `/api/knowledge/evipedia/match?${params.toString()}`,
    { auth: "expert" },
  );
}

export async function deleteKnowledgeNode(nodeId: string) {
  return apiFetch<{ ok: boolean; id: string }>(`/api/knowledge/nodes/${nodeId}`, {
    method: "DELETE",
    auth: "expert",
  });
}

export async function deleteKnowledgeQa(ticketId: string) {
  return apiFetch<{ ok: boolean; id: string }>(`/api/knowledge/qa/${ticketId}`, {
    method: "DELETE",
    auth: "expert",
  });
}

// ── Memory API ────────────────────────────────────────────────────────────────

export type MemoryRecord = {
  id: string;
  user_id: string;
  session_id: string;
  summary: string;
  topics: string[];
  turn_count: number;
  confidence_avg: string;
  created_at: string;
  expires_at: string | null;
};

export type RetentionOption = {
  days: number;
  label: string;
};

export type PrivacySettings = {
  memory_enabled: boolean;
  memory_retention_days: number;
  consented_at?: string;
};

export async function fetchMyMemory() {
  return apiFetch<{ user_id: string; records: MemoryRecord[]; total: number }>("/api/memory", {
    auth: "member",
  });
}

export async function deleteMyMemory() {
  return apiFetch<{ ok: boolean; deleted: number; message: string }>("/api/memory", {
    method: "DELETE",
    auth: "member",
  });
}

export async function fetchRetentionOptions() {
  return apiFetch<{ options: RetentionOption[] }>("/api/memory/retention-options", { auth: false });
}

export async function updatePrivacySettings(settings: { memory_enabled: boolean; memory_retention_days: number }) {
  return apiFetch<{ ok: boolean; privacy_settings: PrivacySettings }>("/api/memory/privacy", {
    method: "PUT",
    auth: "member",
    body: JSON.stringify(settings),
  });
}

export async function closeMemorySession(payload: {
  session_id: string;
  messages: Array<{ role: string; content: string }>;
  member_name?: string;
}) {
  return apiFetch<{ stored: boolean; record?: MemoryRecord; reason?: string }>("/api/memory/session/close", {
    method: "POST",
    auth: "member",
    body: JSON.stringify(payload),
  });
}

export type Ticket = {
  id: string;
  question: string;
  status: string;
  draft_answer: string;
  validated_by?: string;
  category: string;
  created_at: string;
  updated_at: string;
  source?: string;
  from_role?: string;
  from_name?: string;
  assigned_expert_id?: string;
};

export type Expert = {
  id: string;
  name: string;
  role: string;
  specialties: string[];
  status: string;
  status_label: string;
  is_available: boolean;
  default_hours: string;
};

export type KnowledgeNode = {
  id: string;
  title: string;
  category: string;
  summary: string;
  captured_by: string;
  source: string;
  created_at: string;
};

export async function fetchExtractStatus() {
  return apiFetch<{ configured: boolean; model: string }>("/api/extract/status", { auth: false });
}

export type TextIntakeResult = {
  ok: boolean;
  member_data: Record<string, unknown>;
  personal_profile: Partial<PersonalProfile>;
  warnings: string[];
  ai_used: boolean;
};

export async function extractText(text: string) {
  return apiFetch<TextIntakeResult>("/api/extract/text", {
    method: "POST",
    auth: "member",
    body: JSON.stringify({ text }),
  });
}

export async function extractFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    const token = getMemberToken();
    res = await fetch(`${API_BASE}/api/extract`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
  } catch {
    throw new Error("Cannot reach API — run: uvicorn api.main:app --reload --port 8000");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    const detail =
      err && typeof err === "object" && "detail" in err && typeof (err as { detail: string }).detail === "string"
        ? (err as { detail: string }).detail
        : "Extract failed";
    throw new Error(detail);
  }
  return res.json() as Promise<{
    ok: boolean;
    filename?: string;
    field_count?: number;
    fields_found?: string[];
    member_data: Record<string, unknown>;
    warnings: string[];
  }>;
}
