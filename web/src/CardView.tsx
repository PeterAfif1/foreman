import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Card } from "./types";
import { fieldsOf } from "./types";

const URGENCY_STYLE = {
  emergency: "bg-red-600 text-white",
  soon: "bg-amber-500 text-white",
  flexible: "bg-stone-200 text-stone-700 dark:bg-stone-700 dark:text-stone-200",
} as const;

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

export function CardFace({ card, lifted = false }: { card: Card; lifted?: boolean }) {
  const f = fieldsOf(card);
  const name = f?.customer_name ?? (f?.name_hint ? `Maybe ${f.name_hint}` : "No name yet");
  const days = daysSince(card.stage_changed_at);

  return (
    <div
      className={`rounded-lg border border-stone-200 bg-white p-3 text-left shadow-sm dark:border-stone-700 dark:bg-stone-900 ${
        lifted ? "rotate-2 shadow-lg ring-2 ring-accent" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`font-semibold ${f?.customer_name ? "" : "text-stone-500 italic"}`}>
          {name}
        </span>
        {f?.urgency && f.urgency !== "flexible" && (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${URGENCY_STYLE[f.urgency]}`}>
            {f.urgency}
          </span>
        )}
      </div>

      {f && f.job_types.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {f.job_types.map((j) => (
            <span key={j} className="rounded bg-stone-100 px-1.5 py-0.5 text-xs dark:bg-stone-800">
              {j}
            </span>
          ))}
        </div>
      )}

      {/* Plain text: React escapes it, and it comes from strangers. */}
      <p className="mt-1.5 line-clamp-2 text-sm text-stone-600 dark:text-stone-400">{card.text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500">
        {f?.location && <span>{f.location}</span>}
        {card.error && <span className="font-semibold text-red-600">fill in by hand</span>}
        {f && !f.is_lead && <span className="font-semibold">not a lead</span>}
        {card.status === "pending" && !card.error && (
          <span className="rounded-full border border-accent px-1.5 text-[11px] font-semibold text-accent">
            check AI
          </span>
        )}
        {days !== null && days > 0 && <span className="ml-auto">{days}d here</span>}
      </div>
    </div>
  );
}

export function SortableCard({ card, onOpen }: { card: Card; onOpen: (c: Card) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: card.id,
  });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? "opacity-30" : ""}
    >
      <button
        type="button"
        className="block w-full cursor-grab rounded-lg focus-visible:outline-2 focus-visible:outline-blue-600 active:cursor-grabbing"
        onClick={() => onOpen(card)}
        {...attributes}
        {...listeners}
      >
        <CardFace card={card} />
      </button>
    </li>
  );
}
