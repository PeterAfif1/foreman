import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CaretLeftIcon, CaretRightIcon } from "@phosphor-icons/react";
import { SortableCard } from "./CardView";
import type { Card, Stage } from "./types";

export const columnId = (key: string) => `col:${key}`;

/** What an empty column says. The first column is where work starts, so it says how. */
function EmptyColumn({ stage, filtering }: { stage: Stage; filtering: boolean }) {
  if (filtering) return <p className="px-2 py-6 text-center text-sm text-stone-500">No matches</p>;
  if (stage.key === "new")
    return (
      <div className="rounded-lg border border-dashed border-stone-300 px-3 py-6 text-center text-sm text-stone-500 dark:border-stone-700">
        <p className="font-medium text-stone-700 dark:text-stone-300">No new leads</p>
        <p className="mt-1">
          <a href="#/add" className="text-accent underline-offset-2 hover:underline">
            Paste a text or email
          </a>{" "}
          or share the customer chat.
        </p>
      </div>
    );
  return (
    <p className="rounded-lg border border-dashed border-stone-300 px-3 py-6 text-center text-sm text-stone-400 dark:border-stone-800 dark:text-stone-600">
      Drag a card here
    </p>
  );
}

export function Column({
  stage,
  cards,
  dragDisabled,
  collapsed = false,
  onToggle,
  onOpen,
}: {
  stage: Stage;
  cards: Card[];
  /** True while the board is filtered (see Board). */
  dragDisabled: boolean;
  /** Closed columns (Done, Lost) fold into a narrow rail that still takes drops. */
  collapsed?: boolean;
  onToggle?: () => void;
  onOpen: (c: Card) => void;
}) {
  // The whole column is a drop target, so empty and folded columns can receive cards.
  const { setNodeRef, isOver } = useDroppable({ id: columnId(stage.key) });
  const dropRing = isOver ? "ring-2 ring-accent/50" : "";

  if (collapsed)
    return (
      <section ref={setNodeRef} aria-label={stage.name} className={`flex shrink-0 rounded-xl ${dropRing}`}>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={false}
          title={`Show ${stage.name}`}
          className="flex w-11 flex-col items-center gap-2 rounded-xl bg-stone-200/50 py-3 text-stone-500 transition-colors hover:bg-stone-200 hover:text-stone-800 dark:bg-stone-900/40 dark:hover:bg-stone-900 dark:hover:text-stone-200"
        >
          <CaretRightIcon aria-hidden size={14} />
          <span className="text-sm font-semibold [writing-mode:vertical-rl]">{stage.name}</span>
          <span className="font-mono text-xs">{cards.length}</span>
        </button>
      </section>
    );

  return (
    <section
      ref={setNodeRef}
      aria-label={stage.name}
      // Open columns share the width (between 15rem and 20rem each), so wide
      // screens show more of the board before it has to scroll.
      className={`flex max-h-full min-w-60 max-w-80 flex-1 basis-0 flex-col rounded-xl bg-stone-200/60 dark:bg-stone-900/60 ${dropRing}`}
    >
      <header className="flex items-center justify-between gap-2 px-3 pt-3 pb-2">
        <h2 className={`text-sm font-semibold ${stage.closed ? "text-stone-500" : ""}`}>{stage.name}</h2>
        <span className="flex items-center gap-1">
          <span className="font-mono text-xs text-stone-500">{cards.length}</span>
          {onToggle && (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded
              aria-label={`Fold ${stage.name}`}
              className="rounded p-0.5 text-stone-500 hover:bg-stone-300/60 hover:text-stone-800 dark:hover:bg-stone-800 dark:hover:text-stone-200"
            >
              <CaretLeftIcon aria-hidden size={14} />
            </button>
          )}
        </span>
      </header>
      <SortableContext items={cards.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        <ul className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-3">
          {cards.map((card) => (
            <SortableCard key={card.id} card={card} closed={stage.closed} dragDisabled={dragDisabled} onOpen={onOpen} />
          ))}
          {cards.length === 0 && (
            <li>
              <EmptyColumn stage={stage} filtering={dragDisabled} />
            </li>
          )}
        </ul>
      </SortableContext>
    </section>
  );
}

/** Placeholder columns while the board loads, shaped like the real thing. */
export function ColumnSkeleton({ cards }: { cards: number }) {
  return (
    <div aria-hidden className="flex min-w-60 max-w-80 flex-1 basis-0 flex-col gap-2 rounded-xl bg-stone-200/60 p-2 dark:bg-stone-900/60">
      <div className="mx-1 mt-1.5 mb-1 h-4 w-24 rounded bg-stone-300/70 motion-safe:animate-pulse dark:bg-stone-800" />
      {Array.from({ length: cards }, (_, i) => (
        <div key={i} className="h-24 rounded-lg bg-white/70 motion-safe:animate-pulse dark:bg-stone-800/60" />
      ))}
    </div>
  );
}
