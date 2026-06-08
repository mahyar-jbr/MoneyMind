import type {
  WeeklyResponse,
  TransactionsResponse,
  InboxResponse,
  GoalsResponse,
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
