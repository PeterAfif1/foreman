import { useEffect, useState } from "react";
import { api } from "./api";
import type { Usage as UsageData, UsageStats } from "./types";

const FEATURE_NAMES: Record<string, string> = {
  extract: "Reading leads",
  reply: "Reply drafts",
  chat: "Customer chat",
  chat_rewrite: "Chat guardrail rewrites",
};

function money(n: number | null | undefined): string {
  if (n === null || n === undefined) return "n/a";
  if (n === 0) return "$0";
  return n < 1 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

function seconds(ms: number | null): string {
  return ms === null ? "n/a" : `${(ms / 1000).toFixed(1)}s`;
}

function pct(n: number | null): string {
  return n === null ? "n/a" : `${(n * 100).toFixed(n < 0.1 ? 1 : 0)}%`;
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <div className="text-sm text-stone-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {note && <div className="mt-0.5 text-xs text-stone-500">{note}</div>}
    </div>
  );
}

/** One series, so one color and no legend. Bars grow from one baseline. */
function CostChart({ days }: { days: { day: string; cost_usd: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = 180, left = 52, bottom = 22, top = 10;
  const max = Math.max(...days.map((d) => d.cost_usd), 0);
  // Clean round top for the axis: 1, 2 or 5 times a power of ten.
  const step = max === 0 ? 0.001 : (() => {
    const raw = max / 3, p = 10 ** Math.floor(Math.log10(raw));
    return [1, 2, 5, 10].map((m) => m * p).find((s) => s >= raw)!;
  })();
  const yMax = step * Math.ceil(max / step || 1);
  const ticks = [0, 1, 2, 3].map((i) => (yMax / 3) * i);
  const band = (W - left) / days.length;
  const barW = Math.min(24, band * 0.6);
  const y = (v: number) => top + (H - top - bottom) * (1 - v / yMax);
  const label = (d: string) =>
    new Date(d + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="AI cost per day">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={W} y1={y(t)} y2={y(t)} className="stroke-stone-200 dark:stroke-stone-800" strokeWidth={1} />
            <text x={left - 6} y={y(t) + 4} textAnchor="end" className="fill-stone-500 text-[11px]">
              {t === 0 ? "$0" : `$${t.toPrecision(2)}`}
            </text>
          </g>
        ))}
        {days.map((d, i) => {
          const cx = left + band * i + band / 2;
          const h = y(0) - y(d.cost_usd);
          const r = Math.min(4, h);
          const x0 = cx - barW / 2, x1 = cx + barW / 2, yt = y(d.cost_usd), yb = y(0);
          // Rounded at the data end, square at the baseline.
          const path = h <= 0 ? "" :
            `M${x0},${yb} V${yt + r} Q${x0},${yt} ${x0 + r},${yt} H${x1 - r} Q${x1},${yt} ${x1},${yt + r} V${yb} Z`;
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              {/* Hit target: the whole band, bigger than the bar. */}
              <rect x={left + band * i} y={top} width={band} height={H - top - bottom} fill="transparent" />
              {path && <path d={path} className={`fill-[#c2410c] dark:fill-[#ea580c] ${hover === i ? "opacity-80" : ""}`} />}
              {(days.length <= 10 || i % Math.ceil(days.length / 7) === 0) && (
                <text x={cx} y={H - 6} textAnchor="middle" className="fill-stone-500 text-[11px]">
                  {label(d.day)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 rounded-md bg-stone-900 px-2 py-1 text-xs text-white shadow dark:bg-stone-100 dark:text-stone-900"
          style={{ left: `${((left + band * hover + band / 2) / W) * 100}%`, top: 0 }}
        >
          {label(days[hover].day)}: {money(days[hover].cost_usd)}
        </div>
      )}
      <details className="mt-2 text-sm text-stone-500">
        <summary className="cursor-pointer">Show as a table</summary>
        <table className="mt-2 text-left">
          <tbody>
            {days.map((d) => (
              <tr key={d.day}>
                <td className="pr-6">{label(d.day)}</td>
                <td className="tabular-nums">{money(d.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function FeatureRow({ name, s }: { name: string; s: UsageStats }) {
  return (
    <tr className="border-t border-stone-200 dark:border-stone-800">
      <td className="py-2 pr-4">{FEATURE_NAMES[name] ?? name}</td>
      <td className="py-2 pr-4 tabular-nums">{s.calls}</td>
      <td className="py-2 pr-4 tabular-nums">
        {s.errors === 0 ? "0" : `${s.errors} (${pct(s.error_rate)})`}
      </td>
      <td className="py-2 pr-4 tabular-nums">{seconds(s.p50_ms)}</td>
      <td className="py-2 pr-4 tabular-nums">{seconds(s.p95_ms)}</td>
      <td className="py-2 tabular-nums">{money(s.cost_usd)}</td>
    </tr>
  );
}

export function Usage() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState<UsageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.usage(days).then(setData).catch((e) => setError(String(e)));
  }, [days]);

  if (error) return <p className="p-6 text-red-600">{error}</p>;
  if (!data) return <p className="p-6 text-stone-500">Loading...</p>;
  const t = data.total;

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">AI usage</h1>
        <div className="flex gap-1" role="group" aria-label="Time range">
          {[7, 30].map((d) => (
            <button
              key={d}
              type="button"
              aria-pressed={days === d}
              onClick={() => setDays(d)}
              className={`rounded-md px-3 py-1 text-sm ${
                days === d ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900" : "hover:bg-stone-200 dark:hover:bg-stone-800"
              }`}
            >
              Last {d} days
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-sm text-stone-500">
        Every AI call is recorded with its cost, speed and whether it failed. Message text is never stored here.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="AI cost" value={money(t.cost_usd)} note={`last ${days} days`} />
        <Tile label="Cost per lead" value={money(data.cost_per_lead)} note="all AI calls for one card" />
        <Tile label="AI calls" value={String(t.calls)} note={t.errors ? `${t.errors} failed (${pct(t.error_rate)})` : "none failed"} />
        <Tile label="Slowest 5% take" value={seconds(t.p95_ms)} note={`typical: ${seconds(t.p50_ms)}`} />
      </div>

      <h2 className="mt-8 mb-2 text-sm font-semibold text-stone-500 uppercase">Cost per day</h2>
      <div className="rounded-xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        <CostChart days={data.cost_by_day} />
      </div>

      <h2 className="mt-8 mb-2 text-sm font-semibold text-stone-500 uppercase">By feature</h2>
      <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        {Object.keys(data.by_feature).length === 0 ? (
          <p className="text-sm text-stone-500">No AI calls in this period.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-stone-500">
              <tr>
                <th className="pb-2 font-medium">Feature</th>
                <th className="pb-2 font-medium">Calls</th>
                <th className="pb-2 font-medium">Failed</th>
                <th className="pb-2 font-medium">Typical time</th>
                <th className="pb-2 font-medium">Slowest 5%</th>
                <th className="pb-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.by_feature).map(([name, s]) => (
                <FeatureRow key={name} name={name} s={s} />
              ))}
            </tbody>
          </table>
        )}
        {data.guard_rewrites > 0 && (
          <p className="mt-3 text-sm text-stone-500">
            The chat guardrail rewrote {data.guard_rewrites} {data.guard_rewrites === 1 ? "reply" : "replies"} that
            mentioned a price or date the customer never gave.
          </p>
        )}
      </div>

      <h2 className="mt-8 mb-2 text-sm font-semibold text-stone-500 uppercase">Recent failures</h2>
      <div className="rounded-xl border border-stone-200 bg-white p-4 text-sm dark:border-stone-800 dark:bg-stone-900">
        {data.recent_errors.length === 0 ? (
          <p className="text-stone-500">None. Every AI call worked.</p>
        ) : (
          <ul className="space-y-2">
            {data.recent_errors.map((e, i) => (
              <li key={i}>
                <span className="font-medium">{FEATURE_NAMES[e.feature] ?? e.feature}</span>{" "}
                <span className="text-stone-500">{new Date(e.at).toLocaleString()}</span>
                <div className="font-mono text-xs break-words text-stone-600 dark:text-stone-400">{e.error}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
