import { useEffect, useState } from "react";
import type { Card, LeadFields, Urgency } from "./types";
import { EMPTY_FIELDS, JOB_TYPES } from "./types";

const input =
  "w-full rounded-md border border-stone-300 bg-white px-2.5 py-2 text-sm dark:border-stone-700 dark:bg-stone-900";
const changedRing = "border-amber-500 ring-1 ring-amber-500";

function same(a: unknown, b: unknown) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function LeadPanel({
  card,
  stageName,
  onClose,
  onApprove,
}: {
  card: Card;
  stageName: string;
  onClose: () => void;
  onApprove: (fields: LeadFields) => Promise<void>;
}) {
  const base = card.extracted ?? EMPTY_FIELDS;
  const done = card.status === "approved";
  const [f, setF] = useState<LeadFields>(card.approved ?? base);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setF(card.approved ?? card.extracted ?? EMPTY_FIELDS), [card]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = <K extends keyof LeadFields>(k: K, v: LeadFields[K]) => setF((x) => ({ ...x, [k]: v }));
  // Outline anything that differs from what the model returned.
  const ring = (k: keyof LeadFields) =>
    !done &&
    !same(k === "job_types" ? [...f[k]].sort() : f[k], k === "job_types" ? [...base[k]].sort() : base[k])
      ? changedRing
      : "";
  const text = (k: "customer_name" | "contact" | "location" | "scope_summary") => ({
    value: f[k] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(k, e.target.value.trim() === "" ? null : e.target.value),
    disabled: done,
  });
  const money = (k: "budget_min" | "budget_max") => ({
    value: f[k] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      set(k, e.target.value === "" ? null : Math.round(Number(e.target.value))),
    disabled: done,
  });

  async function approve() {
    setSaving(true);
    setError(null);
    try {
      await onApprove({
        ...f,
        customer_name: f.customer_name?.trim() || null,
        contact: f.contact?.trim() || null,
        location: f.location?.trim() || null,
        scope_summary: f.scope_summary?.trim() || null,
        missing_info: f.missing_info.map((s) => s.trim()).filter(Boolean),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        role="dialog"
        aria-label="Lead details"
        className="h-full w-full max-w-xl overflow-y-auto bg-stone-50 p-5 shadow-xl dark:bg-stone-950"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-semibold tracking-wide text-stone-500 uppercase">{stageName}</span>
          <button type="button" onClick={onClose} className="rounded px-2 py-1 text-sm hover:bg-stone-200 dark:hover:bg-stone-800">
            Close
          </button>
        </div>

        {card.error && !done && (
          <p className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            The AI couldn't read this one. Fill it in by hand.
          </p>
        )}
        {done && (
          <p className="mb-3 rounded-md bg-stone-200 p-3 text-sm dark:bg-stone-800">
            {card.edited_fields?.length
              ? `Checked. You fixed: ${card.edited_fields.join(", ").replaceAll("_", " ")}.`
              : "Checked. The AI got everything right."}
          </p>
        )}

        <div className="rounded-lg border border-stone-200 bg-white p-3 text-sm whitespace-pre-wrap break-words dark:border-stone-700 dark:bg-stone-900">
          {card.text}
        </div>
        <p className="mt-1 mb-5 text-xs text-stone-500">
          Received {fmtDate(card.received_at)}
          {card.latency_ms ? ` · read in ${(card.latency_ms / 1000).toFixed(1)}s` : ""}
          {card.prompt_version ? ` · prompt ${card.prompt_version}` : ""}
        </p>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <fieldset className="sm:col-span-2" disabled={done}>
            <legend className="mb-1 text-xs font-semibold text-stone-500 uppercase">Real lead?</legend>
            <div className="flex gap-2">
              {[true, false].map((v) => (
                <button
                  key={String(v)}
                  type="button"
                  onClick={() => set("is_lead", v)}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm ${
                    f.is_lead === v
                      ? "border-stone-900 bg-stone-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900"
                      : "border-stone-300 dark:border-stone-700"
                  }`}
                >
                  {v ? "Yes, a customer" : "No, spam or wrong number"}
                </button>
              ))}
            </div>
          </fieldset>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Name</span>
            <input className={`${input} ${ring("customer_name")}`} {...text("customer_name")} />
            {f.name_hint && !done && f.customer_name !== f.name_hint && (
              <span className="mt-1 block text-xs text-stone-500">
                Maybe {f.name_hint} (from their email){" "}
                <button type="button" className="underline" onClick={() => set("customer_name", f.name_hint)}>
                  Use
                </button>
              </span>
            )}
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Phone or email</span>
            <input className={`${input} ${ring("contact")}`} {...text("contact")} />
          </label>

          <fieldset className={`rounded-md sm:col-span-2 ${ring("job_types")}`} disabled={done}>
            <legend className="mb-1 text-xs font-semibold text-stone-500 uppercase">Job</legend>
            <div className="flex flex-wrap gap-1.5">
              {JOB_TYPES.map((j) => (
                <label key={j} className="flex cursor-pointer items-center gap-1.5 rounded-full bg-stone-200 px-3 py-1 text-sm dark:bg-stone-800">
                  <input
                    type="checkbox"
                    checked={f.job_types.includes(j)}
                    onChange={(e) =>
                      set("job_types", e.target.checked ? [...f.job_types, j] : f.job_types.filter((x) => x !== j))
                    }
                  />
                  {j}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Location</span>
            <input className={`${input} ${ring("location")}`} {...text("location")} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Urgency</span>
            <select
              className={`${input} ${ring("urgency")}`}
              value={f.urgency ?? ""}
              disabled={done}
              onChange={(e) => set("urgency", (e.target.value || null) as Urgency | null)}
            >
              <option value="">Not stated</option>
              <option value="emergency">Emergency</option>
              <option value="soon">Soon</option>
              <option value="flexible">Flexible</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Budget from ($)</span>
            <input type="number" min={0} step={100} className={`${input} ${ring("budget_min")}`} {...money("budget_min")} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Budget up to ($)</span>
            <input type="number" min={0} step={100} className={`${input} ${ring("budget_max")}`} {...money("budget_max")} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Deadline</span>
            <input
              type="date"
              className={`${input} ${ring("deadline")}`}
              value={f.deadline ?? ""}
              disabled={done}
              onChange={(e) => set("deadline", e.target.value || null)}
            />
          </label>
          <div className="hidden sm:block" />
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Summary</span>
            <textarea rows={2} className={`${input} ${ring("scope_summary")}`} {...text("scope_summary")} />
          </label>
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-xs font-semibold text-stone-500 uppercase">Ask the customer (one per line)</span>
            <textarea
              rows={3}
              className={`${input} ${ring("missing_info")}`}
              value={f.missing_info.join("\n")}
              disabled={done}
              onChange={(e) => set("missing_info", e.target.value.split("\n"))}
            />
          </label>
        </div>

        {!done && (
          <div className="mt-5 flex items-center gap-3">
            <button
              type="button"
              disabled={saving}
              onClick={approve}
              className="rounded-md bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-strong disabled:opacity-60"
            >
              {saving ? "Saving..." : "Looks right"}
            </button>
            <span className="text-sm text-stone-500">Saves your fixes. Fixed fields become new test data.</span>
          </div>
        )}
        {error && <p className="mt-2 text-sm text-red-600">Couldn't save: {error}</p>}
      </aside>
    </div>
  );
}
