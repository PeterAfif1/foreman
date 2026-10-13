import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Board, groupByStage, type Columns } from "./Board";
import { LeadPanel } from "./LeadPanel";
import { NewLead } from "./NewLead";
import type { Card, Stage, Stats } from "./types";

export default function App() {
  const [stages, setStages] = useState<Stage[]>([]);
  const [columns, setColumns] = useState<Columns>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
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

  async function onChanged(card: Card) {
    replaceCard(card);
    setStats(await api.stats());
  }

  async function onCreate(text: string, receivedAt: string) {
    const card = await api.create(text, receivedAt);
    await reload();
    setAdding(false);
    setOpenId(card.id);
  }

  const allCards = Object.values(columns).flat();
  const open = allCards.find((c) => c.id === openId) ?? null;
  const toCheck = allCards.filter((c) => c.status === "pending").length;

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-stone-200 bg-white px-4 py-2.5 dark:border-stone-800 dark:bg-stone-900">
        <h1 className="text-lg font-bold">Foreman</h1>
        {stats && (
          <span className="text-sm text-stone-500">
            {stats.total} jobs · {toCheck} to check
            {stats.approved_without_edits_rate !== null &&
              ` · AI right on ${Math.round(stats.approved_without_edits_rate * 100)}% of checked cards`}
          </span>
        )}
        <div className="ml-auto flex gap-2">
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-strong"
          >
            New lead
          </button>
          <button
            type="button"
            onClick={async () => {
              await api.logout();
              window.location.href = "/login";
            }}
            className="rounded-md px-3 py-1.5 text-sm hover:bg-stone-100 dark:hover:bg-stone-800"
          >
            Sign out
          </button>
        </div>
      </header>

      {error && (
        <div role="alert" className="bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      <main className="min-h-0 flex-1">
        <Board stages={stages} columns={columns} setColumns={setColumns} onMove={onMove} onOpen={(c) => setOpenId(c.id)} />
      </main>

      {open && (
        <LeadPanel
          card={open}
          stages={stages}
          onClose={() => setOpenId(null)}
          onChanged={onChanged}
          onMove={onMove}
        />
      )}
      {adding && <NewLead onClose={() => setAdding(false)} onCreate={onCreate} />}
    </div>
  );
}
