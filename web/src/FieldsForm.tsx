import { CheckIcon } from "@phosphor-icons/react";
import type { LeadFields, Urgency } from "./types";
import { JOB_TYPES } from "./types";

const input =
  "w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm transition-colors focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none placeholder:font-sans placeholder:text-stone-400 placeholder:italic dark:placeholder:text-stone-500 disabled:bg-stone-100 disabled:text-stone-700 dark:border-stone-700 dark:bg-stone-900 dark:disabled:bg-stone-900/50 dark:disabled:text-stone-300";
const changedRing = "border-amber-500 ring-1 ring-amber-500";
const label = "mb-1.5 block text-sm font-medium text-stone-700 dark:text-stone-300";
const help = "mt-1 block text-xs text-stone-500";

/** 30000 -> "30,000". Anything typed that isn't a digit is dropped, so "$30,000" reads as 30000. */
const showMoney = (n: number | null) => (n === null ? "" : n.toLocaleString("en-US"));
const readMoney = (s: string) => {
  const digits = s.replace(/\D/g, "");
  return digits ? Number(digits) : null;
};

function norm(k: keyof LeadFields, v: LeadFields[keyof LeadFields]) {
  return JSON.stringify(k === "job_types" ? [...(v as string[])].sort() : v);
}

/** Trim text and drop empty lines before saving. */
export function cleanFields(f: LeadFields): LeadFields {
  return {
    ...f,
    customer_name: f.customer_name?.trim() || null,
    contact: f.contact?.trim() || null,
    location: f.location?.trim() || null,
    scope_summary: f.scope_summary?.trim() || null,
    missing_info: f.missing_info.map((s) => s.trim()).filter(Boolean),
  };
}

export function FieldsForm({
  value: f,
  base,
  disabled,
  blankHint,
  onChange,
}: {
  value: LeadFields;
  /** What changes are compared against: outlined fields differ from this. */
  base: LeadFields;
  disabled: boolean;
  /** Placeholder for empty fields, e.g. "Not in the message" while checking the AI. */
  blankHint?: string;
  onChange: (f: LeadFields) => void;
}) {
  const set = <K extends keyof LeadFields>(k: K, v: LeadFields[K]) => onChange({ ...f, [k]: v });
  const ring = (k: keyof LeadFields) => (!disabled && norm(k, f[k]) !== norm(k, base[k]) ? changedRing : "");
  const text = (k: "customer_name" | "contact" | "location" | "scope_summary") => ({
    value: f[k] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(k, e.target.value.trim() === "" ? null : e.target.value),
    disabled,
    placeholder: blankHint,
  });
  // Text, not type="number": number inputs can't show "30,000" and change value on scroll.
  const money = (k: "budget_min" | "budget_max") => ({
    type: "text",
    inputMode: "numeric" as const,
    value: showMoney(f[k]),
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(k, readMoney(e.target.value)),
    disabled,
    placeholder: blankHint,
  });

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <fieldset className="sm:col-span-2" disabled={disabled}>
        <legend className={label}>Real lead?</legend>
        <div className="flex gap-2">
          {[true, false].map((v) => (
            <button
              key={String(v)}
              type="button"
              onClick={() => set("is_lead", v)}
              aria-pressed={f.is_lead === v}
              className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors active:scale-[0.98] ${
                f.is_lead === v
                  ? "border-accent bg-accent/10 text-accent-strong dark:text-orange-300"
                  : "border-stone-300 text-stone-600 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-400 dark:hover:bg-stone-800"
              }`}
            >
              {v ? "Yes, a customer" : "No, spam or wrong number"}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="block">
        <span className={label}>Name</span>
        <input className={`${input} ${ring("customer_name")}`} {...text("customer_name")} />
        {f.name_hint && !disabled && f.customer_name !== f.name_hint && (
          <span className={help}>
            Maybe {f.name_hint} (from their email){" "}
            <button type="button" className="underline" onClick={() => set("customer_name", f.name_hint)}>
              Use
            </button>
          </span>
        )}
      </label>
      <label className="block">
        <span className={label}>Phone or email</span>
        <input className={`${input} font-mono ${ring("contact")}`} {...text("contact")} />
      </label>

      <fieldset className={`rounded-md sm:col-span-2 ${ring("job_types")}`} disabled={disabled}>
        <legend className={label}>Job</legend>
        <div className="flex flex-wrap gap-1.5">
          {JOB_TYPES.map((j) => {
            const on = f.job_types.includes(j);
            return (
              <button
                key={j}
                type="button"
                aria-pressed={on}
                onClick={() => set("job_types", on ? f.job_types.filter((x) => x !== j) : [...f.job_types, j])}
                className={`flex items-center gap-1 rounded-full border px-3 py-1 text-sm capitalize transition-colors active:scale-[0.98] disabled:cursor-default ${
                  on
                    ? "border-accent bg-accent/10 font-medium text-accent-strong dark:text-orange-300"
                    : "border-stone-300 text-stone-600 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-400 dark:hover:bg-stone-800"
                }`}
              >
                {on && <CheckIcon aria-hidden size={14} weight="bold" />}
                {j}
              </button>
            );
          })}
        </div>
      </fieldset>

      <label className="block">
        <span className={label}>Location</span>
        <input className={`${input} ${ring("location")}`} {...text("location")} />
      </label>
      <label className="block">
        <span className={label}>Urgency</span>
        <select
          className={`${input} ${ring("urgency")}`}
          value={f.urgency ?? ""}
          disabled={disabled}
          onChange={(e) => set("urgency", (e.target.value || null) as Urgency | null)}
        >
          <option value="">Not stated</option>
          <option value="emergency">Emergency</option>
          <option value="soon">Soon</option>
          <option value="flexible">Flexible</option>
        </select>
      </label>
      <label className="block">
        <span className={label}>Budget from</span>
        <span className="relative block">
          <span aria-hidden className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-stone-400">
            $
          </span>
          <input className={`${input} pl-6 font-mono ${ring("budget_min")}`} {...money("budget_min")} />
        </span>
      </label>
      <label className="block">
        <span className={label}>Budget up to</span>
        <span className="relative block">
          <span aria-hidden className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-stone-400">
            $
          </span>
          <input className={`${input} pl-6 font-mono ${ring("budget_max")}`} {...money("budget_max")} />
        </span>
      </label>
      <label className="block">
        <span className={label}>Deadline</span>
        <input
          type="date"
          className={`${input} font-mono ${ring("deadline")}`}
          value={f.deadline ?? ""}
          disabled={disabled}
          onChange={(e) => set("deadline", e.target.value || null)}
        />
      </label>
      <div className="hidden sm:block" />
      <label className="block sm:col-span-2">
        <span className={label}>Summary</span>
        <textarea rows={2} className={`${input} ${ring("scope_summary")}`} {...text("scope_summary")} />
      </label>
      <label className="block sm:col-span-2">
        <span className={label}>Questions for the customer</span>
        <textarea
          rows={3}
          className={`${input} ${ring("missing_info")}`}
          value={f.missing_info.join("\n")}
          disabled={disabled}
          onChange={(e) => set("missing_info", e.target.value.split("\n"))}
        />
        <span className={help}>One per line. The reply draft asks these.</span>
      </label>
    </div>
  );
}
