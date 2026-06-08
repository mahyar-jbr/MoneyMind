import type {
  WeeklyResponse,
  TransactionsResponse,
  InboxResponse,
  GoalsResponse,
  BudgetsResponse,
  IngestStatementResponse,
} from "./types";

// these hit our own /api proxy routes, which add auth and call the backend
export async function getWeekly(signal?: AbortSignal): Promise<WeeklyResponse> {
  const res = await fetch("/api/agg/weekly", { signal });
  if (!res.ok) throw new Error(`weekly failed: ${res.status}`);
  return res.json();
}

export async function getTransactions(
  limit = 25,
  signal?: AbortSignal,
): Promise<TransactionsResponse> {
  const res = await fetch(`/api/transactions?limit=${limit}`, { signal });
  if (!res.ok) throw new Error(`transactions failed: ${res.status}`);
  return res.json();
}

export async function getInbox(
  limit = 20,
  signal?: AbortSignal,
): Promise<InboxResponse> {
  const res = await fetch(`/api/inbox?limit=${limit}`, { signal });
  if (!res.ok) throw new Error(`inbox failed: ${res.status}`);
  return res.json();
}

// V1 — Goals read path. status defaults to "active" so paused/complete/
// abandoned goals are hidden from the dashboard render. Pass "all" to
// include everything.
export async function getGoals(
  status: "active" | "paused" | "complete" | "abandoned" | "all" = "active",
  signal?: AbortSignal,
): Promise<GoalsResponse> {
  const res = await fetch(`/api/goals?status=${status}`, { signal });
  if (!res.ok) throw new Error(`goals failed: ${res.status}`);
  return res.json();
}

// V6 — Budgets read path. status defaults to "active" so abandoned budgets
// are hidden from the dashboard render.
export async function getBudgets(
  status: "active" | "abandoned" | "all" = "active",
  signal?: AbortSignal,
): Promise<BudgetsResponse> {
  const res = await fetch(`/api/budgets?status=${status}`, { signal });
  if (!res.ok) throw new Error(`budgets failed: ${res.status}`);
  return res.json();
}

// V4 — Bank-statement PDF upload. Multipart POST to our Vercel proxy
// which forwards to the backend /ingest/statement route. Server-side
// runs Gemini multimodal extraction + categorization + dedupe + bulk
// insert. Returns a structured summary the chat surfaces as a system
// card.
export async function uploadStatement(
  file: File,
  signal?: AbortSignal,
): Promise<IngestStatementResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  const res = await fetch("/api/ingest/statement", {
    method: "POST",
    body: form,
    signal,
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ error: `upload failed: ${res.status}` }));
    throw new Error(body.error ?? `upload failed: ${res.status}`);
  }
  return res.json();
}
