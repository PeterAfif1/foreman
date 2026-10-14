import { useState } from "react";
import { api } from "./api";
import type { Card, EstimateResult } from "./types";

const money = (n: number) => `$${n.toLocaleString()}`;

const NO_ESTIMATE: Record<string, string> = {
  not_enough: "Not enough similar past jobs to estimate this one.",
  multiple_jobs: "This card has more than one job. Estimates work one job at a time.",
  not_a_lead: "No estimate for spam or wrong numbers.",
};

export function EstimateBox({ card, onDone }: { card: Card; onDone: () => void }) {
  const [result, setResult] = useState<EstimateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.estimate(card.id));
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {!result && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={run}
            disabled={busy}
            className="rounded-md border border-stone-300 px-4 py-2 text-sm font-semibold hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-800"
          >
            {busy ? "Looking at past jobs..." : "Estimate from past jobs"}
          </button>
          <span className="text-sm text-stone-500">Only you see this. Customers never get a price from Foreman.</span>
        </div>
      )}

      {result && result.status !== "ok" && (
        <p className="rounded-md bg-stone-200 p-3 text-sm dark:bg-stone-800">
          {NO_ESTIMATE[result.status] ?? "No estimate."}
          {result.reason && <span className="mt-1 block text-stone-600 dark:text-stone-400">{result.reason}</span>}
        </p>
      )}

      {result && result.status === "ok" && result.low !== null && result.high !== null && (
        <div className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-700 dark:bg-stone-900">
          <div className="text-xs font-semibold text-stone-500 uppercase">Rough range, not a quote</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">
            {result.low === result.high ? money(result.low) : `${money(result.low)} to ${money(result.high)}`}
          </div>
          <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">{result.reason}</p>

          <div className="mt-3 text-xs font-semibold text-stone-500 uppercase">
            Based on {result.cited.length} past {result.cited.length === 1 ? "job" : "jobs"}
          </div>
          <ul className="mt-1 divide-y divide-stone-200 text-sm dark:divide-stone-800">
            {result.cited.map((q) => (
              <li key={q.id} className="flex gap-3 py-2">
                <span className="shrink-0 font-mono text-xs text-stone-500">{q.id}</span>
                <span className="flex-1">
                  {q.description}
                  <span className="block text-xs text-stone-500">
                    {q.location}, {new Date(q.date + "T12:00:00").toLocaleDateString(undefined, { month: "short", year: "numeric" })}
                  </span>
                </span>
                <span className="shrink-0 font-semibold tabular-nums">{money(q.price)}</span>
              </li>
            ))}
          </ul>
          {result.synthetic_data && (
            <p className="mt-2 text-xs text-stone-500">Demo data: these past jobs and prices are made up.</p>
          )}
        </div>
      )}

      {result && (
        <button type="button" className="mt-2 text-sm text-stone-500 underline" onClick={run} disabled={busy}>
          {busy ? "Looking..." : "Run again"}
        </button>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
