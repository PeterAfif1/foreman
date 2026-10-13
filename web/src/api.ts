import type { Card, CardEvent, Draft, LeadFields, Stage, Stats } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (r.status === 401) {
    window.location.href = "/login";
    throw new Error("signed out");
  }
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  stages: () => call<Stage[]>("/api/stages"),
  leads: () => call<Card[]>("/api/leads"),
  stats: () => call<Stats>("/api/stats"),
  create: (text: string, receivedAt: string) =>
    post<Card>("/api/leads", { text, received_at: receivedAt }),
  move: (id: number, stage: string, index: number) =>
    post<Card>(`/api/leads/${id}/move`, { stage, index }),
  approve: (id: number, fields: LeadFields) => post<Card>(`/api/leads/${id}/approve`, fields),
  update: (id: number, fields: LeadFields) =>
    call<Card>(`/api/leads/${id}/fields`, { method: "PUT", body: JSON.stringify(fields) }),
  events: (id: number) => call<CardEvent[]>(`/api/leads/${id}/events`),
  note: (id: number, text: string) => post<CardEvent>(`/api/leads/${id}/notes`, { text }),
  draft: (id: number) => post<Draft>(`/api/leads/${id}/reply`, {}),
  sent: (id: number, text: string) => post<Card>(`/api/leads/${id}/reply/sent`, { text }),
  logout: () => fetch("/logout", { method: "POST" }),
};
