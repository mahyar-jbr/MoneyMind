import type { WeeklyResponse, TransactionsResponse } from "./types";

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
