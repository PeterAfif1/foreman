export const JOB_TYPES = [
  "kitchen",
  "bathroom",
  "roofing",
  "flooring",
  "addition",
  "repair",
  "other",
] as const;
export type JobType = (typeof JOB_TYPES)[number];
export type Urgency = "emergency" | "soon" | "flexible";

// Mirrors foreman/schema.py
export interface LeadFields {
  is_lead: boolean;
  customer_name: string | null;
  name_hint: string | null;
  contact: string | null;
  job_types: JobType[];
  location: string | null;
  budget_min: number | null;
  budget_max: number | null;
  deadline: string | null;
  urgency: Urgency | null;
  scope_summary: string | null;
  missing_info: string[];
}

export const SOURCES = [
  ["text", "Text"],
  ["email", "Email"],
  ["call", "Phone call"],
  ["in_person", "In person"],
  ["other", "Other"],
] as const;
export type Source = (typeof SOURCES)[number][0] | "chat";

export function sourceLabel(source: string | null): string | null {
  if (source === "chat") return "website chat";
  return SOURCES.find(([k]) => k === source)?.[1].toLowerCase() ?? null;
}

export interface Card {
  id: number;
  text: string;
  received_at: string;
  created_at: string;
  status: "pending" | "approved";
  extracted: LeadFields | null;
  approved: LeadFields | null;
  edited_fields: string[] | null;
  model: string | null;
  prompt_version: string | null;
  cost_usd: number | null;
  latency_ms: number | null;
  error: string | null;
  stage: string;
  position: number;
  stage_changed_at: string | null;
  source: Source | null;
}

export interface Stage {
  key: string;
  name: string;
  position: number;
  closed: boolean;
}

export type CardEvent =
  | { at: string; kind: "created"; detail: Record<string, never> }
  | { at: string; kind: "approved"; detail: { edited_fields: string[] } }
  | { at: string; kind: "moved"; detail: { from: string; to: string } }
  | { at: string; kind: "note"; detail: { text: string } }
  | { at: string; kind: "edited"; detail: { fields: string[] } }
  | { at: string; kind: "reply_drafted"; detail: { text: string; prompt: string } }
  | { at: string; kind: "reply_sent"; detail: { text: string; from_draft: boolean; edited: boolean } }
  | {
      at: string;
      kind: "estimated";
      detail: { status: string; low: number | null; high: number | null; cited: string[] };
    };

export interface Draft {
  text: string;
  asks: string[];
  prompt_version: string;
  cost_usd: number | null;
}

export interface Stats {
  total: number;
  pending: number;
  approved: number;
  approved_without_edits_rate: number | null;
}

/** What the card currently says: the reviewed version if there is one. */
export function fieldsOf(card: Card): LeadFields | null {
  return card.approved ?? card.extracted;
}

export const EMPTY_FIELDS: LeadFields = {
  is_lead: true,
  customer_name: null,
  name_hint: null,
  contact: null,
  job_types: [],
  location: null,
  budget_min: null,
  budget_max: null,
  deadline: null,
  urgency: null,
  scope_summary: null,
  missing_info: [],
};

export interface UsageStats {
  calls: number;
  errors: number;
  error_rate: number | null;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  p50_ms: number | null;
  p95_ms: number | null;
}

export interface Usage {
  days: number;
  total: UsageStats;
  by_feature: Record<string, UsageStats>;
  cost_by_day: { day: string; cost_usd: number }[];
  cost_per_lead: number | null;
  guard_rewrites: number;
  recent_errors: { at: string; feature: string; error: string }[];
}

export interface EstimateResult {
  status: "ok" | "not_enough" | "multiple_jobs" | "not_a_lead";
  low: number | null;
  high: number | null;
  reason: string;
  cited: { id: string; description: string; price: number; date: string; location: string }[];
  synthetic_data: boolean;
  prompt_version: string;
}
