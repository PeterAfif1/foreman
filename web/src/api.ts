import type {
  Card,
  CardEvent,
  Draft,
  EstimateResult,
  LeadFields,
  Source,
  Stage,
  Stats,
  Usage,
} from "./types";

/** A failed request, with a message written for the person using the board. */
export class ApiError extends Error {
  constructor(
    message: string,
    /** HTTP status, or 0 when the server couldn't be reached at all. */
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** FastAPI puts the reason in `detail`: a string, or a list for validation errors. */
async function reasonFrom(r: Response): Promise<string | null> {
  try {
    const body = await r.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return null;
}

async function toError(r: Response): Promise<ApiError> {
  // In development Vite answers 502 when the backend isn't running.
  if (r.status === 502 || r.status === 503 || r.status === 504)
    return new ApiError("The server isn't responding. If you run it yourself, check that the backend is started.", r.status);
  if (r.status >= 500) return new ApiError("Something went wrong on the server. Try again in a moment.", r.status);
  const reason = await reasonFrom(r);
  if (r.status === 404) return new ApiError(reason === "lead not found" ? "That card no longer exists." : "Not found.", 404);
  const sentence = reason ? reason.charAt(0).toUpperCase() + reason.slice(1) : `Request failed (${r.status}).`;
  return new ApiError(sentence, r.status);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Can't reach Foreman. Check your connection and try again.", 0);
  }
  if (r.status === 401) {
    window.location.href = "/login";
    throw new ApiError("Signed out.", 401);
  }
  if (!r.ok) throw await toError(r);
  return r.json() as Promise<T>;
}

/** The message to show for anything a request or handler threw. */
export function messageOf(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

const post = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  stages: () => call<Stage[]>("/api/stages"),
  leads: () => call<Card[]>("/api/leads"),
  stats: () => call<Stats>("/api/stats"),
  // getTimezoneOffset is minutes *behind* UTC, so flip the sign.
  usage: (days: number) => call<Usage>(`/api/usage?days=${days}&tz=${-new Date().getTimezoneOffset()}`),
  create: (text: string, receivedAt: string, source: Source | null) =>
    post<Card>("/api/leads", { text, received_at: receivedAt, source }),
  move: (id: number, stage: string, index: number) =>
    post<Card>(`/api/leads/${id}/move`, { stage, index }),
  /** Have the AI read an unchecked card again, e.g. after its model call failed. */
  reextract: (id: number) => post<Card>(`/api/leads/${id}/extract`, {}),
  approve: (id: number, fields: LeadFields) => post<Card>(`/api/leads/${id}/approve`, fields),
  update: (id: number, fields: LeadFields) =>
    call<Card>(`/api/leads/${id}/fields`, { method: "PUT", body: JSON.stringify(fields) }),
  events: (id: number) => call<CardEvent[]>(`/api/leads/${id}/events`),
  note: (id: number, text: string) => post<CardEvent>(`/api/leads/${id}/notes`, { text }),
  draft: (id: number) => post<Draft>(`/api/leads/${id}/reply`, {}),
  sent: (id: number, text: string) => post<Card>(`/api/leads/${id}/reply/sent`, { text }),
  estimate: (id: number) => post<EstimateResult>(`/api/leads/${id}/estimate`, {}),
  logout: () => fetch("/logout", { method: "POST" }),
};
