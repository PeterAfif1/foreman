import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Board, groupByStage, type Columns } from "./Board";
import { AddLead } from "./AddLead";
import { LeadPanel } from "./LeadPanel";
import { go, useRoute } from "./route";
import type { Card, Stage, Stats } from "./types";

function NavLink({ active, href, children }: { active: boolean; href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-md px-3 py-1.5 text-sm font-medium ${
        active ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900" : "hover:bg-stone-100 dark:hover:bg-stone-800"
      }`}
    >
      {children}
    </a>
  );
}

function TabLink({ active, href, icon, children }: { active: boolean; href: string; icon: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-semibold ${active ? "text-accent" : "text-stone-500"}`}
    >
      <span aria-hidden className="text-xl leading-none">
        {icon}
      </span>
      {children}
    </a>
  );
}

export default function App() {
  const [stages, setStages] = useState<Stage[]>([]);
  const [columns, setColumns] = useState<Columns>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const route = useRoute();
  const openId = route.page === "board" ? route.card : null;
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [s, cards, st] = await Promise.all([api.stages(), api.leads(), api.stats()]);
      setStages(s);
      setColumns(groupByStage(s, cards));
      setStats(st);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
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

  async function onMove(id: number, stage: string, index: number) {
    try {
      const card = await api.move(id, stage, index);
      // Dragging already put the card in place. A move from the card's own menu
      // didn't, so reload the board to show it in its new column.
      const shownIn = Object.keys(columns).find((k) => columns[k].some((c) => c.id === id));
      if (shownIn === card.stage) replaceCard(card);
      else await reload();
    } catch (e) {
      // The server is the source of truth: if the move didn't save, show what did.
      setError(`Couldn't move that card: ${e instanceof Error ? e.message : e}`);
      reload();
    }
  }

  // Some changes move the card too (sending the first reply moves it to
  // Contacted), so redraw the board if it's no longer in the column shown.
  async function onChanged(card: Card) {
    const shownIn = Object.keys(columns).find((k) => columns[k].some((c) => c.id === card.id));
    if (shownIn === card.stage) {
      replaceCard(card);
      setStats(await api.stats());
    } else {
      await reload();
    }
  }

  const allCards = Object.values(columns).flat();
  const open = allCards.find((c) => c.id === openId) ?? null;
  const toCheck = allCards.filter((c) => c.status === "pending").length;

  const onBoard = route.page === "board";

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-x-3 border-b border-stone-200 bg-white px-4 py-2.5 dark:border-stone-800 dark:bg-stone-900">
        <a href="#/board" className="text-lg font-bold">
          Foreman
        </a>
        <nav aria-label="Main" className="hidden gap-1 sm:flex">
          <NavLink active={onBoard} href="#/board">
            Board
          </NavLink>
          <NavLink active={!onBoard} href="#/add">
            Add a lead
          </NavLink>
          <a
            href="/quote"
            target="_blank"
            rel="noopener"
            className="rounded-md px-3 py-1.5 text-sm font-medium hover:bg-stone-100 dark:hover:bg-stone-800"
          >
            Customer chat ↗
          </a>
        </nav>
        {stats && onBoard && (
          <span className="hidden text-sm text-stone-500 lg:inline">
            {stats.total} jobs · {toCheck} to check
            {stats.approved_without_edits_rate !== null &&
              ` · AI right on ${Math.round(stats.approved_without_edits_rate * 100)}% of checked cards`}
          </span>
        )}
        {onBoard && toCheck > 0 && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900 lg:hidden dark:bg-amber-900 dark:text-amber-100">
            {toCheck} to check
          </span>
        )}
        <button
          type="button"
          onClick={async () => {
            await api.logout();
            window.location.href = "/login";
          }}
          className="ml-auto rounded-md px-3 py-1.5 text-sm hover:bg-stone-100 dark:hover:bg-stone-800"
        >
          Sign out
        </button>
      </header>

      {error && (
        <div role="alert" className="bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      <main className="min-h-0 flex-1 overflow-y-auto">
        {onBoard ? (
          <Board
            stages={stages}
            columns={columns}
            setColumns={setColumns}
            onMove={onMove}
            onOpen={(c) => go({ page: "board", card: c.id })}
          />
        ) : (
          <AddLead onAdded={reload} />
        )}
      </main>

      {/* On phones the menu sits at the bottom, where thumbs reach. */}
      <nav
        aria-label="Main"
        className="flex border-t border-stone-200 bg-white pb-[env(safe-area-inset-bottom)] sm:hidden dark:border-stone-800 dark:bg-stone-900"
      >
        <TabLink active={onBoard} href="#/board" icon="▦">
          Board
        </TabLink>
        <TabLink active={!onBoard} href="#/add" icon="＋">
          Add a lead
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
