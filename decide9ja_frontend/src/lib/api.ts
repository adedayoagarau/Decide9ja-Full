/**
 * API client for Decide9ja backend (Railway)
 * All data is fetched dynamically - no hardcoded data
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://decide9ja.up.railway.app';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ─── Health ───────────────────────────────────────────────
export async function getHealth() {
  return apiFetch<{ status: string }>('/health');
}

export async function getDetailedHealth() {
  return apiFetch<any>('/health/detailed');
}

// ─── Issues ───────────────────────────────────────────────
export interface Issue {
  issue_id: string;
  title: string;
  domain: string;
  severity: string;
  status: string;
  location?: string;
  states?: string[];
  summary: string;
  first_reported?: string;
  last_updated?: string;
  event_count: number;
  source_count: number;
  verified: boolean;
}

export interface IssueDetail extends Issue {
  events: IssueEvent[];
  politicians: any[];
}

export interface IssueEvent {
  event_id: string;
  title: string;
  description: string;
  event_date: string;
  event_type: string;
  source_url?: string;
  source_name?: string;
  politicians?: any[];
  confidence: number;
}

export async function getIssues(params?: {
  domain?: string;
  state?: string;
  severity?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.domain) searchParams.set('domain', params.domain);
  if (params?.state) searchParams.set('state', params.state);
  if (params?.severity) searchParams.set('severity', params.severity);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));
  const qs = searchParams.toString();
  return apiFetch<{ issues: Issue[]; total: number }>(`/api/issues${qs ? `?${qs}` : ''}`);
}

export async function getIssueDomains() {
  return apiFetch<{ domains: { domain: string; count: number }[] }>('/api/issues/domains');
}

export async function getTrendingIssues(limit = 10) {
  return apiFetch<{ issues: Issue[] }>(`/api/issues/trending?limit=${limit}`);
}

export async function getIssueDetail(issueId: string) {
  return apiFetch<IssueDetail>(`/api/issues/${issueId}`);
}

// ─── Search ───────────────────────────────────────────────
export async function getSearchSuggestions(q: string) {
  return apiFetch<any>(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
}

export async function getTrendingSearches(limit = 20) {
  return apiFetch<any>(`/api/search/trending?limit=${limit}`);
}

export async function advancedSearch(params: {
  query: string;
  states?: string[];
  parties?: string[];
  types?: string[];
  domains?: string[];
  limit?: number;
}) {
  return apiFetch<any>('/api/search/advanced', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ─── Chat ─────────────────────────────────────────────────
export interface ChatResponse {
  response: string;
  session_id: string;
  tools_used?: string[];
  response_time_ms?: number;
}

export async function sendChatMessage(message: string, sessionId?: string) {
  return apiFetch<ChatResponse>('/api/chat/send', {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId || undefined,
    }),
  });
}

export async function getChatHistory(sessionId: string) {
  return apiFetch<any>(`/api/chat/history/${sessionId}`);
}

export async function createChatSession() {
  return apiFetch<{ session_id: string }>('/api/chat/session/new', {
    method: 'POST',
  });
}

// ─── Bills ────────────────────────────────────────────────
export interface Bill {
  bill_id: string;
  title: string;
  short_title?: string;
  description?: string;
  bill_type?: string;
  chamber: string;
  sponsor_slug?: string;
  sponsor_name?: string;
  category?: string;
  status: string;
  introduced_date?: string;
  tags?: string[];
}

export async function getBills(params?: {
  chamber?: string;
  status?: string;
  category?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.chamber) searchParams.set('chamber', params.chamber);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.search) searchParams.set('search', params.search);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));
  const qs = searchParams.toString();
  return apiFetch<{ bills: Bill[]; total: number }>(`/api/bills${qs ? `?${qs}` : ''}`);
}

export async function getBillDetail(billId: string) {
  return apiFetch<any>(`/api/bills/${billId}`);
}

// ─── Compare Politicians ──────────────────────────────────
export async function comparePoliticians(slugs: string[]) {
  return apiFetch<any>('/api/compare', {
    method: 'POST',
    body: JSON.stringify({ slugs }),
  });
}

export async function getSuggestedComparisons() {
  return apiFetch<any>('/api/compare/suggested');
}

// ─── Constituency ─────────────────────────────────────────
export async function getConstituency(state: string, lga: string) {
  return apiFetch<any>(`/api/constituency/${encodeURIComponent(state)}/${encodeURIComponent(lga)}`);
}

// ─── Election Analytics ───────────────────────────────────
export async function getElectionDashboard() {
  return apiFetch<any>('/api/v1/election/dashboard');
}

export async function getElectionCandidates() {
  return apiFetch<any>('/api/v1/election/candidates');
}

export async function getTrendingTopics(category?: string) {
  return apiFetch<any>(`/api/v1/election/trending${category ? `?category=${category}` : ''}`);
}

// ─── Admin / Dashboard ────────────────────────────────────
export async function getAdminMetrics() {
  return apiFetch<any>('/api/admin/metrics');
}

export async function getDashboardOverview() {
  return apiFetch<any>('/api/dashboard/overview');
}

export async function getDashboardFull() {
  return apiFetch<any>('/api/dashboard/full');
}

export async function getMessageTrends() {
  return apiFetch<any>('/api/dashboard/trends/messages');
}

export async function getResponseTimeTrends() {
  return apiFetch<any>('/api/dashboard/trends/response-times');
}

// ─── RAG Query ────────────────────────────────────────────
export async function askQuestion(question: string) {
  return apiFetch<any>('/ask', {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

export async function searchWithWeb(query: string) {
  return apiFetch<any>('/search', {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

// ─── Chatbot Features ─────────────────────────────────────
export async function getELI5(topic: string) {
  return apiFetch<any>(`/api/chatbot/eli5/${encodeURIComponent(topic)}`);
}

export async function getExploreTopics() {
  return apiFetch<any>('/api/chatbot/explore/topics');
}
