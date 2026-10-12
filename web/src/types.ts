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
}

export interface Stage {
  key: string;
  name: string;
  position: number;
  closed: boolean;
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
