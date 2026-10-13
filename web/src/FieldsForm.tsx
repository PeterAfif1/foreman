import type { LeadFields, Urgency } from "./types";
import { JOB_TYPES } from "./types";

const input =
  "w-full rounded-md border border-stone-300 bg-white px-2.5 py-2 text-sm disabled:bg-stone-100 disabled:text-stone-700 dark:border-stone-700 dark:bg-stone-900 dark:disabled:bg-stone-900/50 dark:disabled:text-stone-300";
const changedRing = "border-amber-500 ring-1 ring-amber-500";
const label = "mb-1 block text-xs font-semibold text-stone-500 uppercase";

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
  onChange,
}: {
  value: LeadFields;
  /** What changes are compared against: outlined fields differ from this. */
  base: LeadFields;
  disabled: boolean;
  onChange: (f: LeadFields) => void;
}) {
  const set = <K extends keyof LeadFields>(k: K, v: LeadFields[K]) => onChange({ ...f, [k]: v });
  const ring = (k: keyof LeadFields) => (!disabled && norm(k, f[k]) !== norm(k, base[k]) ? changedRing : "");
  const text = (k: "customer_name" | "contact" | "location" | "scope_summary") => ({
    value: f[k] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(k, e.target.value.trim() === "" ? null : e.target.value),
    disabled,
  });
  const money = (k: "budget_min" | "budget_max") => ({
    value: f[k] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      set(k, e.target.value === "" ? null : Math.round(Number(e.target.value))),
    disabled,
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
        <span className={label}>Name</span>
        <input className={`${input} ${ring("customer_name")}`} {...text("customer_name")} />
        {f.name_hint && !disabled && f.customer_name !== f.name_hint && (
          <span className="mt-1 block text-xs text-stone-500">
            Maybe {f.name_hint} (from their email){" "}
            <button type="button" className="underline" onClick={() => set("customer_name", f.name_hint)}>
              Use
            </button>
          </span>
        )}
      </label>
      <label className="block">
        <span className={label}>Phone or email</span>
        <input className={`${input} ${ring("contact")}`} {...text("contact")} />
      </label>

      <fieldset className={`rounded-md sm:col-span-2 ${ring("job_types")}`} disabled={disabled}>
        <legend className={label}>Job</legend>
        <div className="flex flex-wrap gap-1.5">
          {JOB_TYPES.map((j) => (
            <label
              key={j}
              className="flex cursor-pointer items-center gap-1.5 rounded-full bg-stone-200 px-3 py-1 text-sm dark:bg-stone-800"
            >
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
        <span className={label}>Budget from ($)</span>
        <input type="number" min={0} step={100} className={`${input} ${ring("budget_min")}`} {...money("budget_min")} />
      </label>
      <label className="block">
        <span className={label}>Budget up to ($)</span>
        <input type="number" min={0} step={100} className={`${input} ${ring("budget_max")}`} {...money("budget_max")} />
      </label>
      <label className="block">
        <span className={label}>Deadline</span>
        <input
          type="date"
          className={`${input} ${ring("deadline")}`}
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
        <span className={label}>Ask the customer (one per line)</span>
        <textarea
          rows={3}
          className={`${input} ${ring("missing_info")}`}
          value={f.missing_info.join("\n")}
          disabled={disabled}
          onChange={(e) => set("missing_info", e.target.value.split("\n"))}
        />
      </label>
    </div>
  );
}
