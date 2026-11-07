import { useCallback, useEffect, useRef, useState } from "react";
import { Activity } from "./Activity";
import { api, messageOf } from "./api";
import { cleanFields, FieldsForm } from "./FieldsForm";
import { EstimateBox } from "./EstimateBox";
import { ReplyBox } from "./ReplyBox";
import { useToast } from "./Toast";
import type { Card, CardEvent, LeadFields, Stage } from "./types";
import { EMPTY_FIELDS, sourceLabel } from "./types";

const heading = "mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase";
const primary =
  "rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-strong active:scale-[0.98] disabled:opacity-60";

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

type Tab = "details" | "reply" | "estimate" | "activity";

/** Tabs with the keyboard behavior screen reader users expect: arrows move between them. */
function TabBar({
  tabs,
  current,
  onSelect,
}: {
  tabs: { id: Tab; label: string; count?: number }[];
  current: Tab;
  onSelect: (t: Tab) => void;
}) {
  const refs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({});
  function onKeyDown(e: React.KeyboardEvent) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const i = tabs.findIndex((t) => t.id === current);
    const next = tabs[(i + step + tabs.length) % tabs.length].id;
    onSelect(next);
    refs.current[next]?.focus();
  }
  return (
    <div
      role="tablist"
      aria-label="Card sections"
      onKeyDown={onKeyDown}
      className="sticky top-0 z-10 flex gap-1 overflow-x-auto border-b border-stone-200 bg-stone-50 px-3 sm:px-5 lg:static dark:border-stone-800 dark:bg-stone-950"
    >
      {tabs.map((t) => {
        const selected = t.id === current;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-controls={`panel-${t.id}`}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onSelect(t.id)}
            className={`-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              selected
                ? "border-accent text-stone-900 dark:text-stone-100"
                : "border-transparent text-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
            }`}
          >
            {t.label}
            {t.count ? (
              <span className="rounded-full bg-stone-200 px-1.5 text-xs text-stone-600 dark:bg-stone-800 dark:text-stone-300">
                {t.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function LeadPanel({
  card,
  stages,
  onClose,
  onChanged,
  onMove,
}: {
  card: Card;
  stages: Stage[];
  onClose: () => void;
  /** Called with the saved card after any change, so the board updates. */
  onChanged: (card: Card) => void;
  onMove: (id: number, stage: string, index: number) => Promise<void>;
}) {
  const checked = card.status === "approved";
  const saved = card.approved ?? card.extracted ?? EMPTY_FIELDS;
  const [fields, setFields] = useState<LeadFields>(saved);
  const [editing, setEditing] = useState(false);
  const [events, setEvents] = useState<CardEvent[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("details");
  const toast = useToast();

  const loadEvents = useCallback(() => api.events(card.id).then(setEvents).catch(() => {}), [card.id]);

  // Reset the form when another card opens or this one is saved elsewhere.
  useEffect(() => {
    setFields(card.approved ?? card.extracted ?? EMPTY_FIELDS);
    setEditing(false);
  }, [card]);
  // A different card starts on its details.
  useEffect(() => setTab("details"), [card.id]);
  useEffect(() => {
    loadEvents();
  }, [loadEvents, card]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  /** Run a change, then confirm it with `done` (if given) once it has saved. */
  async function run(action: () => Promise<Card | void>, done?: string) {
    setBusy(true);
    setError(null);
    try {
      const updated = await action();
      if (updated) onChanged(updated);
      await loadEvents();
      if (done) toast(done);
      return true;
    } catch (e) {
      setError(messageOf(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const approve = () => run(() => api.approve(card.id, cleanFields(fields)), "Card checked");
  const saveEdit = async () => {
    if (await run(() => api.update(card.id, cleanFields(fields)), "Changes saved")) setEditing(false);
  };
  const readAgain = () =>
    run(async () => {
      const updated = await api.reextract(card.id);
      toast(updated.error ? "The AI still couldn't read it" : "The AI filled in the card. Check it below.");
      return updated;
    });
  const addNote = async () => {
    if (!note.trim()) return;
    if (await run(async () => void (await api.note(card.id, note.trim())), "Note added")) setNote("");
  };

  // Before checking: outline differences from the AI. While editing: from the saved card.
  const base = checked ? saved : (card.extracted ?? EMPTY_FIELDS);
  const locked = checked && !editing;

  // Replies and estimates only make sense for real customers.
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "details", label: "Details" },
    ...(saved.is_lead
      ? [
          { id: "reply" as const, label: "Reply" },
          { id: "estimate" as const, label: "Estimate" },
        ]
      : []),
    { id: "activity", label: "Activity", count: events.length },
  ];
  const current = tabs.some((t) => t.id === tab) ? tab : "details";
  const panel = (id: Tab) => ({
    role: "tabpanel",
    id: `panel-${id}`,
    "aria-labelledby": `tab-${id}`,
    hidden: current !== id,
  });

  const title = saved.customer_name ?? (saved.name_hint ? `Maybe ${saved.name_hint}` : "No name yet");

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-stone-950/40" onClick={onClose}>
      <aside
        role="dialog"
        aria-label={`Job card: ${title}`}
        className="flex h-full w-full max-w-xl flex-col bg-stone-50 shadow-2xl shadow-stone-950/30 lg:max-w-5xl dark:bg-stone-950"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center gap-3 border-b border-stone-200 px-4 py-3 sm:px-5 dark:border-stone-800">
          <h2 className={`min-w-0 truncate text-lg font-semibold ${saved.customer_name ? "" : "text-stone-500 italic"}`}>
            {title}
          </h2>
          <label className="flex shrink-0 items-center gap-2 text-sm">
            <span className="sr-only">Column</span>
            <select
              value={card.stage}
              onChange={(e) => run(async () => void (await onMove(card.id, e.target.value, 0)))}
              className="rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm font-semibold dark:border-stone-700 dark:bg-stone-900"
            >
              {stages.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto shrink-0 rounded px-2 py-1 text-sm hover:bg-stone-200 dark:hover:bg-stone-800"
          >
            Close
          </button>
        </header>

        {/* Phones: one scrolling column. Wide screens: the message stays in view on the
            left while the details are checked against it on the right. */}
        <div className="min-h-0 flex-1 overflow-y-auto lg:grid lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:overflow-hidden">
          <section
            aria-label="Customer's message"
            className="border-b border-stone-200 p-4 sm:p-5 lg:overflow-y-auto lg:border-r lg:border-b-0 dark:border-stone-800"
          >
            <h3 className={heading}>Message</h3>
            {/* Plain text: React escapes it, and it comes from strangers. */}
            <div className="max-h-48 overflow-y-auto rounded-lg border border-stone-200 bg-white p-3 text-sm leading-relaxed whitespace-pre-wrap break-words lg:max-h-none dark:border-stone-700 dark:bg-stone-900">
              {card.text}
            </div>
            <p className="mt-2 text-xs text-stone-500">
              Received {fmtDate(card.received_at)}
              {card.source ? ` by ${sourceLabel(card.source)}` : ""}
              {card.latency_ms ? ` · read in ${(card.latency_ms / 1000).toFixed(1)}s` : ""}
              {card.prompt_version ? ` · prompt ${card.prompt_version}` : ""}
            </p>
          </section>

          <div className="lg:flex lg:min-h-0 lg:flex-col">
            <TabBar tabs={tabs} current={current} onSelect={setTab} />

            <div className="p-4 sm:p-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
              <div {...panel("details")}>
                {card.error && !checked && (
                  <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                    <p>The AI couldn't read this one. Try again, or fill it in by hand.</p>
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={readAgain}
                        className="rounded-md bg-red-800 px-3 py-1.5 font-semibold text-white hover:bg-red-900 active:scale-[0.98] disabled:opacity-60 dark:bg-red-200 dark:text-red-950 dark:hover:bg-red-100"
                      >
                        {busy ? "Reading..." : "Try the AI again"}
                      </button>
                      {/* The technical reason, for whoever runs the server. */}
                      <details className="min-w-0 text-xs">
                        <summary className="cursor-pointer">What went wrong</summary>
                        <code className="mt-1 block break-words">{card.error}</code>
                      </details>
                    </div>
                  </div>
                )}

                {!checked && !card.error && (
                  <p className="mb-4 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
                    Filled in by the AI. Check it against the message, fix anything wrong, then confirm.
                  </p>
                )}
                {checked && !editing && (
                  <div className="mb-4 flex items-baseline justify-between gap-3">
                    <p className="text-sm text-stone-500">
                      {card.edited_fields?.length
                        ? `When checked, you fixed: ${card.edited_fields.join(", ").replaceAll("_", " ")}.`
                        : "When checked, the AI had everything right."}
                    </p>
                    <button type="button" onClick={() => setEditing(true)} className="shrink-0 text-sm underline">
                      Edit
                    </button>
                  </div>
                )}
                <FieldsForm value={fields} base={base} disabled={locked} onChange={setFields} />

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  {!checked && (
                    <button type="button" disabled={busy} onClick={approve} className={primary}>
                      {busy ? "Saving..." : "Looks right"}
                    </button>
                  )}
                  {editing && (
                    <>
                      <button type="button" disabled={busy} onClick={saveEdit} className={primary}>
                        {busy ? "Saving..." : "Save changes"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setFields(saved);
                          setEditing(false);
                        }}
                        className="rounded-md px-3 py-2 text-sm hover:bg-stone-200 dark:hover:bg-stone-800"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
                {error && <p className="mt-2 text-sm text-red-600">Couldn't save: {error}</p>}
              </div>

              {saved.is_lead && (
                <div {...panel("reply")}>
                  <ReplyBox
                    card={card}
                    contact={saved.contact}
                    busy={busy || editing}
                    onDrafted={loadEvents}
                    onSent={async (updated) => {
                      onChanged(updated);
                      await loadEvents();
                      toast("Marked as sent");
                    }}
                  />
                </div>
              )}

              {saved.is_lead && (
                <div {...panel("estimate")}>
                  <EstimateBox key={card.id} card={card} onDone={loadEvents} />
                </div>
              )}

              <div {...panel("activity")}>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    addNote();
                  }}
                >
                  <label htmlFor="note" className={heading}>
                    Add a note
                  </label>
                  <textarea
                    id="note"
                    rows={2}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Called back, left a voicemail..."
                    className="w-full rounded-md border border-stone-300 bg-white p-2.5 text-sm dark:border-stone-700 dark:bg-stone-900"
                  />
                  <button type="submit" disabled={busy || !note.trim()} className={`${primary} mt-2`}>
                    Add note
                  </button>
                </form>
                <h3 className={`${heading} mt-8`}>History</h3>
                <Activity events={events} stages={stages} />
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
