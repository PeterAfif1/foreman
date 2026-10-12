import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type UniqueIdentifier,
} from "@dnd-kit/core";
import { arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { useRef, useState } from "react";
import { CardFace } from "./CardView";
import { Column } from "./Column";
import type { Card, Stage } from "./types";

export type Columns = Record<string, Card[]>;

export function groupByStage(stages: Stage[], cards: Card[]): Columns {
  const cols: Columns = Object.fromEntries(stages.map((s) => [s.key, []]));
  for (const c of cards) (cols[c.stage] ??= []).push(c);
  return cols;
}

export function Board({
  stages,
  columns,
  setColumns,
  onMove,
  onOpen,
}: {
  stages: Stage[];
  columns: Columns;
  setColumns: (update: (cols: Columns) => Columns) => void;
  onMove: (id: number, stage: string, index: number) => Promise<void>;
  onOpen: (c: Card) => void;
}) {
  const [active, setActive] = useState<Card | null>(null);
  const origin = useRef<{ stage: string; index: number } | null>(null);
  // The board before the drag, to put back if the drag is cancelled (Escape).
  const snapshot = useRef<Columns | null>(null);

  const sensors = useSensors(
    // A small move threshold so a tap still opens the card.
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    // On phones, press and hold to drag, so swiping still scrolls the board.
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const stageOf = (id: UniqueIdentifier): string | undefined => {
    if (typeof id === "string" && id.startsWith("col:")) return id.slice(4);
    return Object.keys(columns).find((k) => columns[k].some((c) => c.id === id));
  };

  function onDragStart({ active }: DragStartEvent) {
    const stage = stageOf(active.id)!;
    const index = columns[stage].findIndex((c) => c.id === active.id);
    origin.current = { stage, index };
    snapshot.current = columns;
    setActive(columns[stage][index]);
  }

  // Moving across columns happens live while dragging, so the gap opens where
  // the card will land.
  function onDragOver({ active, over }: DragOverEvent) {
    if (!over) return;
    const from = stageOf(active.id);
    const to = stageOf(over.id);
    if (!from || !to || from === to) return;
    setColumns((cols) => {
      const card = cols[from].find((c) => c.id === active.id);
      if (!card) return cols;
      const target = cols[to];
      const overIndex = target.findIndex((c) => c.id === over.id);
      const at = overIndex >= 0 ? overIndex : target.length;
      return {
        ...cols,
        [from]: cols[from].filter((c) => c.id !== active.id),
        [to]: [...target.slice(0, at), { ...card, stage: to }, ...target.slice(at)],
      };
    });
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    setActive(null);
    const stage = stageOf(active.id);
    if (!stage || !over) return;
    let cards = columns[stage];
    const from = cards.findIndex((c) => c.id === active.id);
    const to = cards.findIndex((c) => c.id === over.id);
    if (to >= 0 && from !== to) {
      cards = arrayMove(cards, from, to);
      setColumns((cols) => ({ ...cols, [stage]: cards }));
    }
    const index = cards.findIndex((c) => c.id === active.id);
    const start = origin.current;
    if (start && start.stage === stage && start.index === index) return;
    onMove(active.id as number, stage, index);
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
      onDragCancel={() => {
        setActive(null);
        if (snapshot.current) {
          const before = snapshot.current;
          setColumns(() => before);
        }
      }}
    >
      <div className="flex h-full gap-3 overflow-x-auto p-3 sm:p-4">
        {stages.map((s) => (
          <Column key={s.key} stage={s} cards={columns[s.key] ?? []} onOpen={onOpen} />
        ))}
      </div>
      <DragOverlay>{active ? <CardFace card={active} lifted /> : null}</DragOverlay>
    </DndContext>
  );
}
