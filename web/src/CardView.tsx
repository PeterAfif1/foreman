import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ChatTextIcon,
  ClockIcon,
  EnvelopeSimpleIcon,
  EyeIcon,
  GlobeIcon,
  MapPinIcon,
  PaperPlaneTiltIcon,
  PencilSimpleIcon,
  PhoneIcon,
  UserIcon,
  type Icon,
} from "@phosphor-icons/react";
import { daysSince, nextStep, type StepKind } from "./nextStep";
import type { Card, Source } from "./types";
import { fieldsOf, sourceLabel } from "./types";

const SOURCE_ICON: Record<Source, Icon> = {
  text: ChatTextIcon,
  email: EnvelopeSimpleIcon,
  call: PhoneIcon,
  in_person: UserIcon,
  chat: GlobeIcon,
  other: ChatTextIcon,
};

const STEP_ICON: Record<StepKind, Icon> = {
  fill_in: PencilSimpleIcon,
  check_ai: EyeIcon,
  reply: PaperPlaneTiltIcon,
  stale: ClockIcon,
};

const TONE = {
  problem: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  needs_you: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
} as const;

export function CardFace({ card, closed, lifted = false }: { card: Card; closed: boolean; lifted?: boolean }) {
  const f = fieldsOf(card);
  const name = f?.customer_name ?? (f?.name_hint ? `Maybe ${f.name_hint}` : "No name yet");
  const step = nextStep(card, closed);
  const days = daysSince(card.stage_changed_at);
  const Source = card.source ? SOURCE_ICON[card.source] : null;
  const StepGlyph = step ? STEP_ICON[step.kind] : null;

  return (
    <div
      className={`rounded-lg border bg-white p-3 text-left transition-shadow dark:bg-stone-900 ${
        lifted
          ? "rotate-2 border-accent shadow-xl shadow-stone-950/20"
          : "border-stone-200 shadow-sm shadow-stone-950/5 hover:shadow-md dark:border-stone-800"
      } ${closed ? "opacity-70" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`min-w-0 truncate font-semibold ${f?.customer_name ? "" : "font-normal text-stone-500 italic"}`}>
          {name}
        </span>
        {step && StepGlyph && (
          <span
            className={`flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${TONE[step.tone]}`}
          >
            <StepGlyph aria-hidden size={12} weight="bold" />
            {step.label}
          </span>
        )}
      </div>

      {f && (f.job_types.length > 0 || (f.urgency && f.urgency !== "flexible")) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
          {f.urgency === "emergency" && <span className="font-semibold text-red-600 dark:text-red-400">Emergency</span>}
          {f.urgency === "soon" && <span className="font-semibold text-amber-700 dark:text-amber-400">Soon</span>}
          {f.job_types.map((j) => (
            <span key={j} className="rounded bg-stone-100 px-1.5 py-0.5 capitalize text-stone-700 dark:bg-stone-800 dark:text-stone-300">
              {j}
            </span>
          ))}
        </div>
      )}

      {/* Plain text: React escapes it, and it comes from strangers. */}
      <p className="mt-1.5 line-clamp-2 text-sm text-stone-600 dark:text-stone-400">{card.text}</p>

      <div className="mt-2 flex items-center gap-3 text-xs text-stone-500">
        {f?.location && (
          <span className="flex min-w-0 items-center gap-1">
            <MapPinIcon aria-hidden size={12} className="shrink-0" />
            <span className="truncate">{f.location}</span>
          </span>
        )}
        {Source && (
          <span className="flex shrink-0 items-center gap-1" title={`By ${sourceLabel(card.source)}`}>
            <Source aria-hidden size={12} />
            <span className="sr-only">by {sourceLabel(card.source)}</span>
          </span>
        )}
        {f && !f.is_lead && <span className="shrink-0 font-semibold">Not a lead</span>}
        {days !== null && days > 0 && step?.kind !== "stale" && (
          <span className="ml-auto shrink-0 font-mono" title={`${days} days in this column`}>
            {days}d
          </span>
        )}
      </div>
    </div>
  );
}

export function SortableCard({ card, closed, onOpen }: { card: Card; closed: boolean; onOpen: (c: Card) => void }) {
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
        className="block w-full cursor-grab rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent active:cursor-grabbing"
        onClick={() => onOpen(card)}
        {...attributes}
        {...listeners}
      >
        <CardFace card={card} closed={closed} />
      </button>
    </li>
  );
}
