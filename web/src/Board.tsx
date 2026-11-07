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
import { useCallback, useEffect, useRef, useState } from "react";
import { BoardFilters, isFiltering, matches, NO_FILTER, type Filter } from "./BoardFilters";
import { CardFace } from "./CardView";
import { Column, ColumnSkeleton } from "./Column";
import { nextStep } from "./nextStep";
import type { Card, Stage } from "./types";

export type Columns = Record<string, Card[]>;
/** Where a card sits: its column and its place in it (0 = top). */
export type Spot = { stage: string; index: number };

export function groupByStage(stages: Stage[], cards: Card[]): Columns {
  const cols: Columns = Object.fromEntries(stages.map((s) => [s.key, []]));
  for (const c of cards) (cols[c.stage] ??= []).push(c);
  return cols;
}

/** Which sides of a scrolling row have more to see, so the edges can fade out. */
function useScrollEdges(deps: unknown[]) {
  const ref = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const update = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const left = el.scrollLeft > 1;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
    setEdges((e) => (e.left === left && e.right === right ? e : { left, right }));
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    update();
    const resize = new ResizeObserver(update);
    resize.observe(el);
    return () => resize.disconnect();
    // Re-measure whenever what's in the row changes (`deps`), not only on resize.
  }, [update, ...deps]);
  return { ref, edges, onScroll: update };
}

const FADE = {
  none: "",
  right: "[mask-image:linear-gradient(to_right,black_calc(100%-3rem),transparent)]",
  left: "[mask-image:linear-gradient(to_left,black_calc(100%-3rem),transparent)]",
  both: "[mask-image:linear-gradient(to_right,transparent,black_3rem,black_calc(100%-3rem),transparent)]",
};

export function Board({
  stages,
  columns,
  loading,
  setColumns,
  onMove,
  onOpen,
}: {
  stages: Stage[];
  /** True until the first load finishes: shows placeholder columns. */
  loading: boolean;
  columns: Columns;
  setColumns: (update: (cols: Columns) => Columns) => void;
  onMove: (id: number, stage: string, index: number, from: Spot | null) => Promise<void>;
  onOpen: (c: Card) => void;
}) {
  const [active, setActive] = useState<Card | null>(null);
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  // Positions are saved per column, so dragging within a filtered column would
  // land cards in the wrong place. Moving still works from the card's menu.
  const filtering = isFiltering(filter);
  const closed = (key: string) => stages.find((s) => s.key === key)?.closed ?? false;
  const shownIn = (key: string) => (columns[key] ?? []).filter((c) => matches(c, filter, closed(key)));
  const all = stages.flatMap((s) => (columns[s.key] ?? []).map((c) => ({ c, closed: s.closed })));
  const needsMeCount = all.filter(({ c, closed }) => nextStep(c, closed)).length;
  const shownCount = stages.reduce((n, s) => n + shownIn(s.key).length, 0);

  // Done and Lost start folded: they fill up over time and rarely need a look.
  // A filter that finds cards in one unfolds it so the matches aren't hidden.
  const [unfolded, setUnfolded] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setUnfolded((open) => {
      const next = new Set(open);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  const folded = (s: Stage) => s.closed && !unfolded.has(s.key) && !(filtering && shownIn(s.key).length > 0);

  const row = useScrollEdges([stages, columns, unfolded, filter, loading]);
  const fade = row.edges.left && row.edges.right ? "both" : row.edges.right ? "right" : row.edges.left ? "left" : "none";
  const origin = useRef<Spot | null>(null);
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
    onMove(active.id as number, stage, index, start);
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
      <div className="flex h-full flex-col">
        <BoardFilters
          filter={filter}
          onChange={setFilter}
          needsMeCount={needsMeCount}
          shown={shownCount}
          total={all.length}
        />
        <div
          ref={row.ref}
          onScroll={row.onScroll}
          className={`flex min-h-0 flex-1 gap-3 overflow-x-auto p-3 sm:p-4 ${FADE[fade]}`}
        >
          {loading
            ? [3, 2, 1, 1].map((n, i) => <ColumnSkeleton key={i} cards={n} />)
            : stages.map((s) => (
                <Column
                  key={s.key}
                  stage={s}
                  cards={shownIn(s.key)}
                  dragDisabled={filtering}
                  collapsed={folded(s)}
                  onToggle={s.closed ? () => toggle(s.key) : undefined}
                  onOpen={onOpen}
                />
              ))}
        </div>
      </div>
      <DragOverlay>
        {active ? (
          <CardFace card={active} closed={stages.find((s) => s.key === active.stage)?.closed ?? false} lifted />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
