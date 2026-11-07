import { MagnifyingGlassIcon, XIcon } from "@phosphor-icons/react";
import { useEffect, useRef } from "react";
import { nextStep } from "./nextStep";
import type { Card, JobType } from "./types";
import { fieldsOf, JOB_TYPES } from "./types";

export interface Filter {
  query: string;
  needsMe: boolean;
  job: JobType | null;
}

export const NO_FILTER: Filter = { query: "", needsMe: false, job: null };

export const isFiltering = (f: Filter) => f.query.trim() !== "" || f.needsMe || f.job !== null;

/** Does the card pass the filter? Every word typed has to appear somewhere on it. */
export function matches(card: Card, filter: Filter, stageClosed: boolean): boolean {
  const f = fieldsOf(card);
  if (filter.needsMe && !nextStep(card, stageClosed)) return false;
  if (filter.job && !f?.job_types.includes(filter.job)) return false;
  const words = filter.query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const haystack = [card.text, f?.customer_name, f?.name_hint, f?.contact, f?.location, f?.scope_summary]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return words.every((w) => haystack.includes(w));
}

const chip = (on: boolean) =>
  `flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors active:scale-[0.98] ${
    on
      ? "border-accent bg-accent/10 font-medium text-accent-strong dark:text-orange-300"
      : "border-stone-300 text-stone-600 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-400 dark:hover:bg-stone-800"
  }`;

export function BoardFilters({
  filter,
  onChange,
  needsMeCount,
  shown,
  total,
}: {
  filter: Filter;
  onChange: (f: Filter) => void;
  needsMeCount: number;
  shown: number;
  total: number;
}) {
  const search = useRef<HTMLInputElement>(null);

  // "/" jumps to search, like most web apps, unless you're already typing somewhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && e.target.closest("input, textarea, select, [contenteditable]");
      if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const active = isFiltering(filter);

  return (
    <div className="flex flex-wrap items-center gap-2 px-3 pt-3 sm:px-4 sm:pt-4">
      <label className="relative w-full sm:w-72">
        <span className="sr-only">Search cards</span>
        <MagnifyingGlassIcon
          aria-hidden
          size={16}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-stone-400"
        />
        <input
          ref={search}
          type="search"
          value={filter.query}
          onChange={(e) => onChange({ ...filter, query: e.target.value })}
          onKeyDown={(e) => e.key === "Escape" && onChange({ ...filter, query: "" })}
          placeholder="Search name, phone, place..."
          className="w-full rounded-md border border-stone-300 bg-white py-1.5 pr-8 pl-9 text-sm transition-colors placeholder:text-stone-400 focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none dark:border-stone-700 dark:bg-stone-900"
        />
        <kbd className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 rounded border border-stone-300 px-1.5 font-mono text-[11px] text-stone-400 sm:block dark:border-stone-700">
          /
        </kbd>
      </label>

      <button
        type="button"
        aria-pressed={filter.needsMe}
        onClick={() => onChange({ ...filter, needsMe: !filter.needsMe })}
        className={chip(filter.needsMe)}
      >
        Needs me
        <span className="rounded-full bg-stone-200 px-1.5 font-mono text-xs text-stone-700 dark:bg-stone-800 dark:text-stone-300">
          {needsMeCount}
        </span>
      </button>

      <label>
        <span className="sr-only">Job type</span>
        <select
          value={filter.job ?? ""}
          onChange={(e) => onChange({ ...filter, job: (e.target.value || null) as JobType | null })}
          className={`${chip(filter.job !== null)} bg-white pr-2 dark:bg-stone-900`}
        >
          <option value="">All jobs</option>
          {JOB_TYPES.map((j) => (
            <option key={j} value={j}>
              {j.charAt(0).toUpperCase() + j.slice(1)}
            </option>
          ))}
        </select>
      </label>

      {active && (
        <>
          <button
            type="button"
            onClick={() => onChange({ ...filter, query: "", needsMe: false, job: null })}
            className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
          >
            <XIcon aria-hidden size={14} />
            Clear
          </button>
          <p aria-live="polite" className="text-sm text-stone-500">
            Showing {shown} of {total}. Drag is paused while filtering.
          </p>
        </>
      )}
    </div>
  );
}
