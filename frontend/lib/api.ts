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

// V4 — Bank-statement PDF upload with **streaming progress**.
//
// Multipart POST → Server-Sent Events response. Each frame the backend
// emits is one phase of the ingest pipeline (received → dedupe →
// extracting → extracted → categorizing → saving → done). The final
// `done` frame's data is the StatementCard payload.
//
// onProgress fires for every non-terminal event so the UI can morph
// the progress timeline. Returns the final IngestStatementResponse
// once `done` arrives (or throws if an `error` event arrives instead).

export type IngestProgressEvent =
  | { type: "received"; filename: string; size_bytes: number }
  | {
      type: "dedupe";
      status: "checking" | "new" | "duplicate";
      prior_count?: number;
      source_hash?: string;
    }
  | { type: "extracting"; model: string }
  | {
      type: "extracted";
      transaction_count: number;
      spend_count: number;
      payment_count: number;
      issuer: string;
      account_last4: string;
      period_start: string | null;
      period_end: string | null;
    }
  | { type: "categorizing"; applied_overrides: boolean; warnings: string[] }
  | { type: "saving"; count: number };

export async function uploadStatement(
  file: File,
  opts?: {
    onProgress?: (event: IngestProgressEvent) => void;
    signal?: AbortSignal;
  },
): Promise<IngestStatementResponse> {
  const form = new FormData();
  form.append("file", file, file.name);

  const res = await fetch("/api/ingest/statement", {
    method: "POST",
    body: form,
    signal: opts?.signal,
  });
  if (!res.ok || !res.body) {
    const body = await res
      .json()
      .catch(() => ({ error: `upload failed: ${res.status}` }));
    throw new Error(body.error ?? `upload failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: IngestStatementResponse | null = null;

  // SSE frames are delimited by `\n\n`. Buffer partial reads until we
  // have at least one full frame, then process all complete frames and
  // keep the trailing remainder for the next read.
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIdx: number;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      const parsed = parseSseFrame(frame);
      if (!parsed) continue;

      if (parsed.event === "error") {
        const message =
          (parsed.data as { message?: string })?.message ??
          "upload failed during processing";
        throw new Error(message);
      }
      if (parsed.event === "done") {
        finalResult = parsed.data as unknown as IngestStatementResponse;
        continue;
      }
      // Non-terminal progress events.
      if (opts?.onProgress) {
        opts.onProgress({
          type: parsed.event,
          ...parsed.data,
        } as IngestProgressEvent);
      }
    }
  }

  if (!finalResult) {
    throw new Error("upload stream ended without a result");
  }
  return finalResult;
}

function parseSseFrame(
  frame: string,
): { event: string; data: Record<string, unknown> } | null {
  let event = "";
  let data: Record<string, unknown> | null = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) {
      event = line.slice("event: ".length).trim();
    } else if (line.startsWith("data: ")) {
      try {
        data = JSON.parse(line.slice("data: ".length));
      } catch {
        return null;
      }
    }
  }
  if (!event || !data) return null;
  return { event, data };
}
