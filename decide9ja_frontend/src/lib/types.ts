/**
 * Shared type definitions for the Decide9ja frontend
 */

export interface Finding {
  id: string;
  type: string;
  entity: string;
  description: string;
  amount: number;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  year: number;
  state?: string;
  recommendation?: string;
  risk_factors?: string[];
  risk_score?: number;
  budget_code?: string;
  confidence?: number;
  analyzer?: string;
  title?: string;
  jurisdiction?: string;
  mda?: string;
  project_name?: string;
  anomaly_type?: string;
  enriched_analysis?: string;
}

export interface ChatMessage {
  type: "system" | "user";
  content: string;
  tools_used?: string[];
  timestamp?: number;
}

export interface Politician {
  slug: string;
  name: string;
  party: string;
  position: string;
  state?: string;
  constituency?: string;
  data?: Record<string, any>;
}

export interface NewsArticle {
  article_id: string;
  title: string;
  url: string;
  source: string;
  excerpt?: string;
  published_date?: string;
  topics?: string[];
  politicians?: string[];
}

export interface AdminMetrics {
  total_users: number;
  active_users_today: number;
  total_conversations: number;
  avg_response_time_ms: number;
  fallback_rate: number;
  state_distribution: Record<string, number>;
  intent_distribution: Record<string, number>;
  daily_active_users: { date: string; count: number }[];
}
