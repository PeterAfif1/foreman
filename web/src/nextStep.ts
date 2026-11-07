import type { Card } from "./types";
import { fieldsOf } from "./types";

/** A card with no movement for this long needs a nudge (matches the "no answer in
 * 6 days" follow-up the events table is kept for). */
export const STALE_AFTER_DAYS = 6;

export type StepKind = "fill_in" | "check_ai" | "reply" | "stale";

export interface Step {
  kind: StepKind;
  label: string;
  /** "problem" is red, "needs_you" is amber. */
  tone: "problem" | "needs_you";
}

export function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

/** The one thing this card needs from a person right now, or null if nothing.
 * Shown as the card's badge and used by the "Needs me" filter. */
export function nextStep(card: Card, stageClosed: boolean): Step | null {
  if (stageClosed) return null;
  if (card.status === "pending")
    return card.error
      ? { kind: "fill_in", label: "Fill in by hand", tone: "problem" }
      : { kind: "check_ai", label: "Check AI", tone: "needs_you" };
  if (!fieldsOf(card)?.is_lead) return null;
  // Sending the first reply moves a card out of New, so a checked card still
  // there hasn't been answered.
  if (card.stage === "new") return { kind: "reply", label: "Reply", tone: "needs_you" };
  const days = daysSince(card.stage_changed_at);
  if (days !== null && days >= STALE_AFTER_DAYS) return { kind: "stale", label: `Stale ${days}d`, tone: "needs_you" };
  return null;
}
