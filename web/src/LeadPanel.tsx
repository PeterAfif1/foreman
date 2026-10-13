import { useCallback, useEffect, useState } from "react";
import { Activity } from "./Activity";
import { api } from "./api";
import { cleanFields, FieldsForm } from "./FieldsForm";
import type { Card, CardEvent, LeadFields, Stage } from "./types";
import { EMPTY_FIELDS } from "./types";

const heading = "mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase";
const primary =
  "rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-60";

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
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

  const loadEvents = useCallback(() => api.events(card.id).then(setEvents).catch(() => {}), [card.id]);

  // Reset the form when another card opens or this one is saved elsewhere.
  useEffect(() => {
    setFields(card.approved ?? card.extracted ?? EMPTY_FIELDS);
    setEditing(false);
  }, [card]);
  useEffect(() => {
    loadEvents();
  }, [loadEvents, card]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function run(action: () => Promise<Card | void>) {
    setBusy(true);
    setError(null);
    try {
      const updated = await action();
      if (updated) onChanged(updated);
      await loadEvents();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const approve = () => run(() => api.approve(card.id, cleanFields(fields)));
  const saveEdit = async () => {
    if (await run(() => api.update(card.id, cleanFields(fields)))) setEditing(false);
  };
  const addNote = async () => {
    if (!note.trim()) return;
    if (await run(async () => void (await api.note(card.id, note.trim())))) setNote("");
  };

  // Before checking: outline differences from the AI. While editing: from the saved card.
  const base = checked ? saved : (card.extracted ?? EMPTY_FIELDS);
  const locked = checked && !editing;

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        role="dialog"
        aria-label="Job card"
        className="h-full w-full max-w-xl overflow-y-auto bg-stone-50 p-5 shadow-xl dark:bg-stone-950"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
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
            className="ml-auto rounded px-2 py-1 text-sm hover:bg-stone-200 dark:hover:bg-stone-800"
          >
            Close
          </button>
        </div>

        {card.error && !checked && (
          <p className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            The AI couldn't read this one. Fill it in by hand.
          </p>
        )}

        <h3 className={heading}>Message</h3>
        <div className="rounded-lg border border-stone-200 bg-white p-3 text-sm whitespace-pre-wrap break-words dark:border-stone-700 dark:bg-stone-900">
          {card.text}
        </div>
        <p className="mt-1 mb-6 text-xs text-stone-500">
          Received {fmtDate(card.received_at)}
          {card.latency_ms ? ` · read in ${(card.latency_ms / 1000).toFixed(1)}s` : ""}
          {card.prompt_version ? ` · prompt ${card.prompt_version}` : ""}
        </p>

        <div className="mb-2 flex items-baseline justify-between">
          <h3 className={heading}>Job details</h3>
          {checked && !editing && (
            <button type="button" onClick={() => setEditing(true)} className="text-sm underline">
              Edit
            </button>
          )}
        </div>
        {!checked && (
          <p className="mb-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
            Filled in by the AI. Check it against the message, fix anything wrong, then confirm.
          </p>
        )}
        <FieldsForm value={fields} base={base} disabled={locked} onChange={setFields} />

        <div className="mt-4 flex flex-wrap items-center gap-3">
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
          {checked && !editing && card.edited_fields && (
            <span className="text-sm text-stone-500">
              {card.edited_fields.length
                ? `When checked, you fixed: ${card.edited_fields.join(", ").replaceAll("_", " ")}.`
                : "When checked, the AI had everything right."}
            </span>
          )}
        </div>
        {error && <p className="mt-2 text-sm text-red-600">Couldn't save: {error}</p>}

        <h3 className={`${heading} mt-8`}>Notes</h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            addNote();
          }}
        >
          <textarea
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

        <h3 className={`${heading} mt-8`}>Activity</h3>
        <Activity events={events} stages={stages} />
      </aside>
    </div>
  );
}
