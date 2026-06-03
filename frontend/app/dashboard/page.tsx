"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Wallet } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { StatCards } from "@/components/dashboard/stat-cards";
import { SpendChart } from "@/components/dashboard/spend-chart";
import { CategoryBreakdown } from "@/components/dashboard/category-breakdown";
import { TransactionsList } from "@/components/dashboard/transactions-list";
import { Inbox } from "@/components/dashboard/inbox";
import { getWeekly, getTransactions, getInbox } from "@/lib/api";
import type { WeekBucket, Transaction, InboxMessage } from "@/lib/types";

type State =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      weeks: WeekBucket[];
      transactions: Transaction[];
      inbox: InboxMessage[];
    };

export default function DashboardPage() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        // inbox is best-effort: if it fails, the dashboard still loads
        const inboxPromise = getInbox(20, ac.signal)
          .then((r) => r.messages ?? [])
          .catch(() => [] as InboxMessage[]);
        const [weekly, tx] = await Promise.all([
          getWeekly(ac.signal),
          getTransactions(25, ac.signal),
        ]);
        setState({
          status: "ready",
          weeks: weekly.weeks ?? [],
          transactions: tx.transactions ?? [],
          inbox: await inboxPromise,
        });
      } catch {
        if (!ac.signal.aborted) setState({ status: "error" });
      }
    })();
    return () => ac.abort();
  }, []);

  const currency =
    state.status === "ready"
      ? state.transactions[0]?.currency ?? "USD"
      : "USD";

  return (
    <AppShell activeHref="/dashboard">
      <div className="mx-auto w-full max-w-6xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-[color:var(--color-fg-muted)]">
            Your spending at a glance.
          </p>
        </div>

        {state.status === "loading" ? <DashboardSkeleton /> : null}
        {state.status === "error" ? <Unavailable /> : null}
        {state.status === "ready" ? (
          state.weeks.length === 0 && state.transactions.length === 0 ? (
            <Empty />
          ) : (
            <div className="flex flex-col gap-6">
              <StatCards
                weeks={state.weeks}
                txCount={state.transactions.length}
                currency={currency}
              />
              <SpendChart weeks={state.weeks} currency={currency} />
              <div className="grid gap-6 lg:grid-cols-2">
                <CategoryBreakdown weeks={state.weeks} currency={currency} />
                <div className="flex flex-col gap-6">
                  <Inbox messages={state.inbox} />
                  <TransactionsList transactions={state.transactions} />
                </div>
              </div>
            </div>
          )
        ) : null}
      </div>
    </AppShell>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40"
          />
        ))}
      </div>
      <div className="h-72 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40" />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="h-64 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40" />
        <div className="h-64 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40" />
      </div>
    </div>
  );
}

function Empty() {
  return (
    <div className="rounded-2xl border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40 p-12 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)]">
        <Wallet className="h-6 w-6" />
      </div>
      <h2 className="mt-3 text-base font-semibold">No data yet</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-[color:var(--color-fg-muted)]">
        Once transactions load, spending shows up here.
      </p>
      <Link
        href="/chat"
        className="mt-4 inline-flex h-10 items-center justify-center rounded-full bg-[color:var(--color-accent)] px-5 text-sm font-semibold text-zinc-950 hover:bg-[color:var(--color-accent-hi)]"
      >
        Try the chat
      </Link>
    </div>
  );
}

function Unavailable() {
  return (
    <div className="rounded-2xl border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40 p-12 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[color:var(--color-surface-hi)] text-[color:var(--color-fg-muted)]">
        <Wallet className="h-6 w-6" />
      </div>
      <h2 className="mt-3 text-base font-semibold">Can&apos;t load your data</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-[color:var(--color-fg-muted)]">
        The service is unavailable right now. Try again in a moment.
      </p>
    </div>
  );
}
