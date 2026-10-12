import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { SortableCard } from "./CardView";
import type { Card, Stage } from "./types";

export const columnId = (key: string) => `col:${key}`;

export function Column({
  stage,
  cards,
  onOpen,
}: {
  stage: Stage;
  cards: Card[];
  onOpen: (c: Card) => void;
}) {
  // The column itself is a drop target too, so empty columns can receive cards.
  const { setNodeRef, isOver } = useDroppable({ id: columnId(stage.key) });

  return (
    <section
      aria-label={stage.name}
      className={`flex max-h-full w-72 shrink-0 flex-col rounded-xl bg-stone-200/70 dark:bg-stone-900/60 ${
        isOver ? "ring-2 ring-accent/40" : ""
      }`}
    >
      <header className="flex items-baseline justify-between px-3 pt-3 pb-2">
        <h2 className={`text-sm font-semibold ${stage.closed ? "text-stone-500" : ""}`}>
          {stage.name}
        </h2>
        <span className="text-xs text-stone-500">{cards.length}</span>
      </header>
      <SortableContext items={cards.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        <ul ref={setNodeRef} className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-3">
          {cards.map((card) => (
            <SortableCard key={card.id} card={card} onOpen={onOpen} />
          ))}
        </ul>
      </SortableContext>
    </section>
  );
}
