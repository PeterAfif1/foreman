import type { CardEvent, Stage } from "./types";

const fields = (list: string[]) => list.join(", ").replaceAll("_", " ");

function when(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  if (mins < 24 * 60) return `${Math.round(mins / 60)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function describe(e: CardEvent, stageName: (key: string) => string): string {
  switch (e.kind) {
    case "created":
      return "Card created from the message";
    case "approved":
      return e.detail.edited_fields.length
        ? `Checked the AI's version, fixed ${fields(e.detail.edited_fields)}`
        : "Checked the AI's version, nothing to fix";
    case "moved":
      return `Moved from ${stageName(e.detail.from)} to ${stageName(e.detail.to)}`;
    case "edited":
      return `Updated ${fields(e.detail.fields)}`;
    case "note":
      return e.detail.text;
    case "reply_drafted":
      return "AI drafted a reply";
    case "reply_sent":
      return e.detail.from_draft && !e.detail.edited
        ? "Sent the AI's draft as is"
        : e.detail.from_draft
          ? "Sent a reply (edited the AI's draft)"
          : "Sent a reply";
  }
}

export function Activity({ events, stages }: { events: CardEvent[]; stages: Stage[] }) {
  const stageName = (key: string) => stages.find((s) => s.key === key)?.name ?? key;
  return (
    <ol className="space-y-3">
      {[...events].reverse().map((e, i) => (
        <li key={`${e.at}-${i}`} className="flex gap-3 text-sm">
          <span
            className={`mt-1.5 size-2 shrink-0 rounded-full ${e.kind === "note" ? "bg-accent" : "bg-stone-400"}`}
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            {e.kind === "reply_sent" && (
              <p className="mb-1 text-stone-700 dark:text-stone-300">{describe(e, stageName)}</p>
            )}
            {e.kind === "note" || e.kind === "reply_sent" ? (
              <p className="rounded-md bg-white p-2 whitespace-pre-wrap break-words shadow-sm dark:bg-stone-900">
                {e.kind === "reply_sent" ? e.detail.text : describe(e, stageName)}
              </p>
            ) : (
              <p className="text-stone-700 dark:text-stone-300">{describe(e, stageName)}</p>
            )}
            <time className="text-xs text-stone-500" dateTime={e.at}>
              {when(e.at)}
            </time>
          </div>
        </li>
      ))}
    </ol>
  );
}
