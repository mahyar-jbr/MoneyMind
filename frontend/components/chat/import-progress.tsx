"use client";

import {
  Brain,
  CheckCircle2,
  Database,
  FileSearch,
  FileText,
  Loader2,
  Sparkles,
  Upload,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { IngestProgressEvent } from "@/lib/api";


// Each row in the progress timeline. The status drives the icon variant
// (idle → spinning → done → error) and the visual progression.
type StepStatus = "idle" | "active" | "done" | "error";

type StepKey =
  | "received"
  | "dedupe"
  | "extracting"
  | "extracted"
  | "categorizing"
  | "saving";


const STEPS: { key: StepKey; label: string; idleHint: string; icon: LucideIcon }[] = [
  {
    key: "received",
    label: "Received",
    idleHint: "Uploading your statement",
    icon: Upload,
  },
  {
    key: "dedupe",
    label: "Checking for duplicates",
    idleHint: "Have we seen this file before?",
    icon: FileSearch,
  },
  {
    key: "extracting",
    label: "Reading the PDF",
    idleHint: "Gemini 2.5 Flash multimodal",
    icon: FileText,
  },
  {
    key: "extracted",
    label: "Transactions found",
    idleHint: "",
    icon: Sparkles,
  },
  {
    key: "categorizing",
    label: "Categorizing",
    idleHint: "Matching merchants against our taxonomy",
    icon: Brain,
  },
  {
    key: "saving",
    label: "Saving to MongoDB Atlas",
    idleHint: "Writing transactions + indexing",
    icon: Database,
  },
];


/**
 * V4 — Import progress card.
 *
 * Vertical timeline that morphs as SSE events arrive. Each step starts
 * idle, becomes active when its event lands, completes when the NEXT
 * step's event arrives (or when `done` flips the whole card to a
 * success state). On error, the active step turns red and the card
 * stops advancing.
 *
 * The `events` prop is the running list of frames the chat page has
 * received so far for THIS upload. The component is purely derived
 * from that list — no internal state — so React StrictMode double-
 * renders stay correct.
 */
export function ImportProgress({
  filename,
  events,
  errorMessage,
  elapsedMs,
}: {
  filename: string;
  events: IngestProgressEvent[];
  errorMessage?: string;
  elapsedMs: number;
}) {
  // Build a map of step → its latest event payload, so each step row
  // can read extracted counts / dedupe status / model name.
  const eventsByStep = new Map<StepKey, IngestProgressEvent>();
  for (const e of events) {
    eventsByStep.set(e.type as StepKey, e);
  }

  // Find the latest step the backend has reached.
  const reachedKeys = new Set(events.map((e) => e.type as StepKey));
  const latestIdx = STEPS.findIndex(
    (s, i) => reachedKeys.has(s.key) && i === STEPS.findLastIndex((x) => reachedKeys.has(x.key)),
  );

  function statusFor(stepIdx: number): StepStatus {
    if (errorMessage && stepIdx === latestIdx) return "error";
    if (stepIdx < latestIdx) return "done";
    if (stepIdx === latestIdx) return "active";
    return "idle";
  }

  // Special-case dedupe-duplicate: the timeline short-circuits.
  const dedupeEvent = eventsByStep.get("dedupe") as
    | { status: "checking" | "new" | "duplicate"; prior_count?: number }
    | undefined;
  const isDuplicateBranch = dedupeEvent?.status === "duplicate";

  return (
    <div className="w-full max-w-md rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[color:var(--color-surface-hi)]/60 to-[color:var(--color-surface)]/40 p-4 shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_24px_60px_-30px_rgba(0,0,0,0.7)] backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)] ring-1 ring-inset ring-[color:var(--color-accent)]/20">
          <FileText className="h-4 w-4" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-semibold">
            {errorMessage ? "Couldn't read this statement" : "Reading your statement"}
          </p>
          <p className="truncate text-xs text-[color:var(--color-fg-muted)]">
            {filename}
          </p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide tabular-nums text-[color:var(--color-fg-muted)]">
          {formatElapsed(elapsedMs)}
        </span>
      </div>

      {/* Timeline */}
      <ol className="mt-4 flex flex-col">
        {STEPS.map((step, idx) => {
          // If we're on the duplicate branch, hide extracting/extracted/
          // categorizing/saving — the pipeline short-circuited.
          if (isDuplicateBranch && idx > 1) return null;

          const status = statusFor(idx);
          const event = eventsByStep.get(step.key);
          const isLast =
            isDuplicateBranch ? idx === 1 : idx === STEPS.length - 1;

          return (
            <li
              key={step.key}
              className="relative flex items-start gap-3 pb-3 last:pb-0"
            >
              {/* Vertical connector line */}
              {!isLast && (
                <div
                  className={`absolute left-3.5 top-7 h-[calc(100%-1.5rem)] w-px ${
                    status === "done"
                      ? "bg-[color:var(--color-accent)]/40"
                      : "bg-white/10"
                  }`}
                />
              )}

              {/* Step bullet */}
              <StepBullet status={status} Icon={step.icon} />

              {/* Step content */}
              <div className="flex-1 min-w-0 pt-0.5">
                <p
                  className={`text-sm font-medium ${
                    status === "idle"
                      ? "text-[color:var(--color-fg-muted)]"
                      : status === "error"
                        ? "text-rose-400"
                        : "text-[color:var(--color-fg)]"
                  }`}
                >
                  {renderStepLabel(step, event, isDuplicateBranch)}
                </p>
                <p
                  className={`mt-0.5 text-xs ${
                    status === "error"
                      ? "text-rose-400/80"
                      : "text-[color:var(--color-fg-muted)]"
                  }`}
                >
                  {renderStepSubtitle(step, event, status, errorMessage)}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}


function StepBullet({
  status,
  Icon,
}: {
  status: StepStatus;
  Icon: LucideIcon;
}) {
  if (status === "done") {
    return (
      <span className="z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[color:var(--color-accent)] text-zinc-950 ring-2 ring-[color:var(--color-surface)]">
        <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2.5} />
      </span>
    );
  }
  if (status === "active") {
    return (
      <span className="z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[color:var(--color-accent)]/15 text-[color:var(--color-accent)] ring-2 ring-[color:var(--color-surface)]">
        <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2.5} />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-rose-400/15 text-rose-400 ring-2 ring-[color:var(--color-surface)]">
        <XCircle className="h-3.5 w-3.5" strokeWidth={2.5} />
      </span>
    );
  }
  // idle
  return (
    <span className="z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white/[0.04] text-[color:var(--color-fg-muted)] ring-2 ring-[color:var(--color-surface)]">
      <Icon className="h-3.5 w-3.5" />
    </span>
  );
}


function renderStepLabel(
  step: { key: StepKey; label: string },
  event: IngestProgressEvent | undefined,
  isDuplicateBranch: boolean,
): string {
  if (step.key === "dedupe" && isDuplicateBranch) {
    return "Already imported";
  }
  if (step.key === "extracted" && event?.type === "extracted") {
    const total = event.transaction_count;
    return `Found ${total} transaction${total === 1 ? "" : "s"}`;
  }
  return step.label;
}


function renderStepSubtitle(
  step: { key: StepKey; idleHint: string },
  event: IngestProgressEvent | undefined,
  status: StepStatus,
  errorMessage: string | undefined,
): string {
  if (status === "error" && errorMessage) {
    return errorMessage;
  }
  if (status === "idle") {
    return step.idleHint;
  }

  // Active or done — surface the live data from this step's event.
  if (event?.type === "received") {
    return `${formatBytes(event.size_bytes)} · ready for the model`;
  }
  if (event?.type === "dedupe") {
    if (event.status === "checking") return "Looking up the file hash";
    if (event.status === "new") return "New statement — proceeding";
    if (event.status === "duplicate")
      return `This file was already imported (${event.prior_count ?? 0} transactions on file)`;
  }
  if (event?.type === "extracting") {
    return `${event.model} reading every line`;
  }
  if (event?.type === "extracted") {
    const parts: string[] = [];
    if (event.spend_count > 0)
      parts.push(`${event.spend_count} charge${event.spend_count === 1 ? "" : "s"}`);
    if (event.payment_count > 0)
      parts.push(
        `${event.payment_count} payment${event.payment_count === 1 ? "" : "s"} (excluded)`,
      );
    if (event.issuer)
      parts.push(`${event.issuer}${event.account_last4 ? ` ·· ${event.account_last4}` : ""}`);
    return parts.join(" · ");
  }
  if (event?.type === "categorizing") {
    return event.warnings.length
      ? event.warnings.join(" · ")
      : "Mapping to food, transport, subscriptions…";
  }
  if (event?.type === "saving") {
    return `Inserting ${event.count} transactions into atlas.transactions`;
  }
  return step.idleHint;
}


function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}


function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m ${r}s`;
}
