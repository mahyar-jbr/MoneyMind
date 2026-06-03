import type {
  WeeklyResponse,
  TransactionsResponse,
  InboxResponse,
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
