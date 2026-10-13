import { useState } from "react";
import { api } from "./api";
import type { Card } from "./types";

const primary =
  "rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-60";
const secondary =
  "rounded-md border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800";

/** sms: or mailto: link that opens the person's own app with the reply typed in. */
function sendLink(contact: string | null, text: string): { href: string; label: string } | null {
  if (!contact) return null;
  const body = encodeURIComponent(text);
  if (contact.includes("@")) return { href: `mailto:${contact.trim()}?body=${body}`, label: "Email it" };
  const digits = contact.replace(/[^\d+]/g, "");
  if (digits.replace("+", "").length >= 7) return { href: `sms:${digits}?&body=${body}`, label: "Text it" };
  return null;
}

export function ReplyBox({
  card,
  contact,
  busy,
  onSent,
  onDrafted,
}: {
  card: Card;
  contact: string | null;
  busy: boolean;
  onSent: (card: Card) => Promise<void>;
  onDrafted: () => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function draft() {
    setWorking(true);
    setError(null);
    try {
      setText((await api.draft(card.id)).text);
      onDrafted();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  }

  async function markSent() {
    if (!text?.trim()) return;
    setWorking(true);
    setError(null);
    try {
      await onSent(await api.sent(card.id, text.trim()));
      setText(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  }

  const link = text ? sendLink(contact, text) : null;

  return (
    <div>
      {text === null ? (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={draft} disabled={working || busy} className={primary}>
            {working ? "Writing..." : "Draft reply"}
          </button>
          <span className="text-sm text-stone-500">The AI asks for whatever is still missing.</span>
        </div>
      ) : (
        <>
          <textarea
            rows={5}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full rounded-md border border-stone-300 bg-white p-2.5 text-sm dark:border-stone-700 dark:bg-stone-900"
          />
          <p className="mt-1 text-xs text-stone-500">
            Edit anything you want. Nothing is sent from here: send it from your phone or email, then mark it as sent.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {link && (
              <a href={link.href} className={primary}>
                {link.label}
              </a>
            )}
            <button
              type="button"
              className={secondary}
              onClick={async () => {
                await navigator.clipboard.writeText(text);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <button type="button" className={secondary} onClick={markSent} disabled={working || !text.trim()}>
              Mark as sent
            </button>
            <button type="button" className={secondary} onClick={draft} disabled={working}>
              Try again
            </button>
            <button type="button" className="px-2 py-2 text-sm text-stone-500 underline" onClick={() => setText(null)}>
              Discard
            </button>
          </div>
        </>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
