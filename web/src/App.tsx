import {
  ArrowUpRightIcon,
  ChartBarIcon,
  KanbanIcon,
  PlusIcon,
  SignOutIcon,
  WarningCircleIcon,
  type Icon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { api, messageOf } from "./api";
import { Board, groupByStage, type Columns, type Spot } from "./Board";
import { AddLead } from "./AddLead";
import { Usage } from "./Usage";
import { LeadPanel } from "./LeadPanel";
import { go, useRoute } from "./route";
import { nextStep } from "./nextStep";
import { useToast } from "./Toast";
import type { Card, Stage } from "./types";

type LinkProps = { active: boolean; href: string; icon: Icon; children: React.ReactNode };

function NavLink({ active, href, icon: Glyph, children }: LinkProps) {
  return (
    <a
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-stone-100 text-stone-900 dark:bg-stone-800 dark:text-stone-50"
          : "text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100"
      }`}
    >
      <Glyph aria-hidden size={16} weight={active ? "bold" : "regular"} />
      {children}
    </a>
  );
}

function TabLink({ active, href, icon: Glyph, children }: LinkProps) {
  return (
    <a
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex flex-1 flex-col items-center gap-1 py-2 text-xs font-semibold ${active ? "text-accent" : "text-stone-500"}`}
    >
      <Glyph aria-hidden size={22} weight={active ? "fill" : "regular"} />
      {children}
    </a>
  );
}

export default function App() {
  const [stages, setStages] = useState<Stage[]>([]);
  const [columns, setColumns] = useState<Columns>({});
  const [loading, setLoading] = useState(true);
  const route = useRoute();
  const openId = route.page === "board" ? route.card : null;
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const reload = useCallback(async () => {
    try {
      const [s, cards] = await Promise.all([api.stages(), api.leads()]);
      setStages(s);
      setColumns(groupByStage(s, cards));
      setError(null);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const replaceCard = (card: Card) =>
    setColumns((cols) => {
      const next: Columns = {};
      for (const [k, list] of Object.entries(cols)) next[k] = list.map((c) => (c.id === card.id ? card : c));
      return next;
    });

  const positionOf = (id: number): Spot | null => {
    for (const [stage, list] of Object.entries(columns)) {
      const index = list.findIndex((c) => c.id === id);
      if (index >= 0) return { stage, index };
    }
    return null;
  };
  const stageName = (key: string) => stages.find((s) => s.key === key)?.name ?? key;

  /** Save a move. `from` is where the card started; a drag knows it, a menu
   * move happens before the board changes, so it's read from the board. */
  async function onMove(id: number, stage: string, index: number, from = positionOf(id)) {
    try {
      const card = await api.move(id, stage, index);
      // Dragging already put the card in place. A move from the card's own menu
      // didn't, so reload the board to show it in its new column.
      const shownIn = positionOf(id)?.stage;
      if (shownIn === card.stage) replaceCard(card);
      else await reload();
      // Reordering within a column isn't worth a message; changing column is.
      if (from && from.stage !== stage) {
        toast(`Moved to ${stageName(stage)}`, {
          label: "Undo",
          run: () => undoMove(id, from),
        });
      }
    } catch (e) {
      // The server is the source of truth: if the move didn't save, show what did.
      // A toast too, because the banner is hidden behind an open card on phones.
      const message = `Couldn't move that card: ${messageOf(e)}`;
      setError(message);
      toast(message);
      reload();
    }
  }

  async function undoMove(id: number, to: Spot) {
    try {
      await api.move(id, to.stage, to.index);
      await reload();
      toast(`Moved back to ${stageName(to.stage)}`);
    } catch (e) {
      const message = `Couldn't undo the move: ${messageOf(e)}`;
      setError(message);
      toast(message);
    }
  }

  // Some changes move the card too (sending the first reply moves it to
  // Contacted), so redraw the board if it's no longer in the column shown.
  async function onChanged(card: Card) {
    const shownIn = Object.keys(columns).find((k) => columns[k].some((c) => c.id === card.id));
    if (shownIn === card.stage) replaceCard(card);
    else await reload();
  }

  const allCards = Object.values(columns).flat();
  const open = allCards.find((c) => c.id === openId) ?? null;
  const closed = (key: string) => stages.find((s) => s.key === key)?.closed ?? false;
  // Same rule as the card badges and the "Needs me" filter.
  const needYou = allCards.filter((c) => nextStep(c, closed(c.stage))).length;
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

  const onBoard = route.page === "board";

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-x-3 border-b border-stone-200 bg-white px-4 py-2.5 dark:border-stone-800 dark:bg-stone-900">
        <a href="#/board" className="text-lg font-bold">
          Foreman
        </a>
        <nav aria-label="Main" className="hidden gap-1 sm:flex">
          <NavLink active={onBoard} href="#/board" icon={KanbanIcon}>
            Board
          </NavLink>
          <NavLink active={route.page === "add"} href="#/add" icon={PlusIcon}>
            Add a lead
          </NavLink>
          <NavLink active={route.page === "usage"} href="#/usage" icon={ChartBarIcon}>
            AI usage
          </NavLink>
          <a
            href="/quote"
            target="_blank"
            rel="noopener"
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium text-stone-600 transition-colors hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100"
          >
            Customer chat
            <ArrowUpRightIcon aria-label="opens in a new tab" size={14} />
          </a>
        </nav>
        {onBoard && !loading && (
          <span className="hidden text-sm text-stone-500 lg:inline">
            {plural(allCards.length, "job", "jobs")}
            {needYou > 0 && ` · ${plural(needYou, "needs", "need")} you`}
          </span>
        )}
        {onBoard && needYou > 0 && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900 lg:hidden dark:bg-amber-950 dark:text-amber-200">
            {plural(needYou, "needs", "need")} you
          </span>
        )}
        <button
          type="button"
          onClick={async () => {
            await api.logout();
            window.location.href = "/login";
          }}
          className="ml-auto flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-stone-600 transition-colors hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100"
        >
          <SignOutIcon aria-hidden size={16} />
          Sign out
        </button>
      </header>

      {error && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200"
        >
          <WarningCircleIcon aria-hidden size={18} className="shrink-0" />
          <span className="min-w-0 flex-1">{error}</span>
          <button
            type="button"
            onClick={reload}
            className="rounded-md bg-red-800 px-3 py-1 font-semibold text-white hover:bg-red-900 active:scale-[0.98] dark:bg-red-200 dark:text-red-950 dark:hover:bg-red-100"
          >
            Try again
          </button>
          <button type="button" onClick={() => setError(null)} className="px-1 underline">
            Dismiss
          </button>
        </div>
      )}

      <main className="min-h-0 flex-1 overflow-y-auto">
        {onBoard ? (
          <Board
            stages={stages}
            columns={columns}
            loading={loading}
            setColumns={setColumns}
            onMove={onMove}
            onOpen={(c) => go({ page: "board", card: c.id })}
          />
        ) : route.page === "add" ? (
          <AddLead onAdded={reload} />
        ) : (
          <Usage />
        )}
      </main>

      {/* On phones the menu sits at the bottom, where thumbs reach. */}
      <nav
        aria-label="Main"
        className="flex border-t border-stone-200 bg-white pb-[env(safe-area-inset-bottom)] sm:hidden dark:border-stone-800 dark:bg-stone-900"
      >
        <TabLink active={onBoard} href="#/board" icon={KanbanIcon}>
          Board
        </TabLink>
        <TabLink active={route.page === "add"} href="#/add" icon={PlusIcon}>
          Add a lead
        </TabLink>
        <TabLink active={route.page === "usage"} href="#/usage" icon={ChartBarIcon}>
          AI usage
        </TabLink>
      </nav>

      {open && (
        <LeadPanel
          card={open}
          stages={stages}
          onClose={() => go({ page: "board", card: null })}
          onChanged={onChanged}
          onMove={onMove}
        />
      )}
    </div>
  );
}
