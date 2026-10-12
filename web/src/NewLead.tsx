import { useState } from "react";

const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time

export function NewLead({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (text: string, receivedAt: string) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [date, setDate] = useState(today());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onCreate(text.trim(), date);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-30 grid place-items-center bg-black/30 p-4" onClick={onClose}>
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl dark:bg-stone-900"
      >
        <h2 className="text-lg font-semibold">New lead</h2>
        <p className="mb-3 text-sm text-stone-500">
          Paste a text, email or your call notes. The AI fills in the card.
        </p>
        <textarea
          autoFocus
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-md border border-stone-300 bg-white p-2.5 text-sm dark:border-stone-700 dark:bg-stone-950"
          placeholder="hey saw ur truck, need a quote on a bathroom..."
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-stone-500">
            Received
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="rounded-md border border-stone-300 bg-white px-2 py-1 dark:border-stone-700 dark:bg-stone-950"
            />
          </label>
          <div className="ml-auto flex gap-2">
            <button type="button" onClick={onClose} className="rounded-md px-3 py-2 text-sm hover:bg-stone-100 dark:hover:bg-stone-800">
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !text.trim()}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-60"
            >
              {busy ? "Reading..." : "Add to board"}
            </button>
          </div>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">Couldn't add it: {error}</p>}
      </form>
    </div>
  );
}
