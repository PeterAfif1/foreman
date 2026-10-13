import { useState } from "react";
import { api } from "./api";
import { go } from "./route";
import type { Card, Source } from "./types";
import { fieldsOf, SOURCES } from "./types";

const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, local time

const PLACEHOLDER: Record<Source | "none", string> = {
  none: "hey saw ur truck, need a quote on a bathroom...",
  text: "Paste the text message here...",
  email: "Paste the email here...",
  call: "Write down what they said on the call: the job, where, when, their number...",
  in_person: "Write down what they asked for...",
  other: "Paste or type what they said...",
  chat: "Paste the conversation here...",
};

export function AddLead({ onAdded }: { onAdded: () => Promise<void> }) {
  const [text, setText] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const [date, setDate] = useState(today());
  const [pickDate, setPickDate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<Card | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const card = await api.create(text.trim(), date, source);
      await onAdded();
      setAdded(card);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function another() {
    setAdded(null);
    setText("");
    setSource(null);
    setDate(today());
    setPickDate(false);
  }

  if (added) return <Added card={added} onAnother={another} />;

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold">Add a lead</h1>
      <p className="mt-1 text-stone-600 dark:text-stone-400">
        Type or paste what the customer said. The AI fills in the card, and you check it after.
      </p>

      <fieldset className="mt-6">
        <legend className="mb-2 text-sm font-semibold">How did they reach you?</legend>
        <div className="flex flex-wrap gap-2">
          {SOURCES.map(([key, name]) => (
            <button
              key={key}
              type="button"
              aria-pressed={source === key}
              onClick={() => setSource(source === key ? null : key)}
              className={`rounded-full border px-4 py-2 text-sm ${
                source === key
                  ? "border-stone-900 bg-stone-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900"
                  : "border-stone-300 bg-white dark:border-stone-700 dark:bg-stone-900"
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="mt-6 block">
        <span className="mb-2 block text-sm font-semibold">What did they say?</span>
        <textarea
          rows={8}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER[source ?? "none"]}
          className="w-full rounded-lg border border-stone-300 bg-white p-3 text-base dark:border-stone-700 dark:bg-stone-900"
        />
      </label>
      <p className="mt-1 text-sm text-stone-500">
        On your phone, tap the microphone on the keyboard to talk instead of typing.
      </p>

      <div className="mt-4 text-sm text-stone-600 dark:text-stone-400">
        {pickDate ? (
          <label className="flex items-center gap-2">
            Received on
            <input
              type="date"
              value={date}
              max={today()}
              onChange={(e) => setDate(e.target.value)}
              className="rounded-md border border-stone-300 bg-white px-2 py-1 dark:border-stone-700 dark:bg-stone-900"
            />
          </label>
        ) : (
          <>
            Received today.{" "}
            <button type="button" className="underline" onClick={() => setPickDate(true)}>
              Change date
            </button>
          </>
        )}
      </div>

      <button
        type="submit"
        disabled={busy || !text.trim()}
        className="mt-6 w-full rounded-lg bg-accent px-6 py-3 text-base font-semibold text-white hover:bg-accent-strong disabled:opacity-60 sm:w-auto"
      >
        {busy ? "Reading it..." : "Add to the board"}
      </button>
      {error && <p className="mt-3 text-sm text-red-600">Couldn't add it: {error}</p>}
    </form>
  );
}

function budget(min: number | null, max: number | null): string | null {
  const $ = (n: number) => `$${n.toLocaleString()}`;
  if (min !== null && max !== null) return min === max ? `about ${$(min)}` : `${$(min)} to ${$(max)}`;
  if (max !== null) return `up to ${$(max)}`;
  if (min !== null) return `at least ${$(min)}`;
  return null;
}

function Added({ card, onAnother }: { card: Card; onAnother: () => void }) {
  const f = fieldsOf(card);
  const rows: [string, string | null][] = f
    ? [
        ["Name", f.customer_name ?? (f.name_hint ? `maybe ${f.name_hint}` : null)],
        ["Contact", f.contact],
        ["Job", f.job_types.join(", ") || null],
        ["Where", f.location],
        ["Budget", budget(f.budget_min, f.budget_max)],
        ["Deadline", f.deadline ? new Date(f.deadline + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : null],
        ["Urgency", f.urgency],
      ]
    : [];

  return (
    <div className="mx-auto max-w-2xl p-4 sm:p-8">
      <p className="text-sm font-semibold text-green-700 dark:text-green-400">Added to New lead</p>
      <h1 className="mt-1 text-2xl font-bold">
        {f && !f.is_lead ? "This looks like spam or a wrong number" : "Here's what the AI got"}
      </h1>

      {card.error ? (
        <p className="mt-4 rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-950 dark:text-red-200">
          The AI couldn't read it, but the message is saved. Open the card to fill it in by hand.
        </p>
      ) : (
        <dl className="mt-4 divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {rows.map(([label, value]) => (
            <div key={label} className="flex gap-4 px-4 py-2.5">
              <dt className="w-20 shrink-0 text-sm text-stone-500">{label}</dt>
              <dd className={value ? "" : "text-stone-400 italic"}>{value ?? "not given"}</dd>
            </div>
          ))}
        </dl>
      )}
      {f && f.missing_info.length > 0 && (
        <p className="mt-3 text-sm text-stone-600 dark:text-stone-400">
          Still to ask: {f.missing_info.join(" ")}
        </p>
      )}

      <div className="mt-6 flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          onClick={() => go({ page: "board", card: card.id })}
          className="rounded-lg bg-accent px-6 py-3 font-semibold text-white hover:bg-accent-strong"
        >
          Open the card
        </button>
        <button
          type="button"
          onClick={onAnother}
          className="rounded-lg border border-stone-300 px-6 py-3 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800"
        >
          Add another
        </button>
      </div>
    </div>
  );
}
