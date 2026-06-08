"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Wallet } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { TransactionsList } from "@/components/dashboard/transactions-list";
import { Inbox } from "@/components/dashboard/inbox";
import {
  BudgetProgress,
  CARD,
  CategoryBreakdown,
  DashboardFilters,
  IncomeExpenses,
  InsightsPanel,
  KpiRow,
  LargestPurchases,
  SavingsGoals,
  TrendChart,
  UpcomingBills,
} from "@/components/dashboard/widgets";
import { getInbox, getTransactions } from "@/lib/api";
import {
  buildBuckets,
  categoriesPresent,
  keyOf,
  type Period,
} from "@/lib/analytics";
import type { InboxMessage, Transaction } from "@/lib/types";

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; transactions: Transaction[]; inbox: InboxMessage[] };

export default function DashboardPage() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [period, setPeriod] = useState<Period>("month");
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [category, setCategory] = useState<string>("all");

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        const inboxPromise = getInbox(20, ac.signal)
          .then((r) => r.messages ?? [])
          .catch(() => [] as InboxMessage[]);
        const tx = await getTransactions(500, ac.signal);
        setState({
          status: "ready",
          transactions: tx.transactions ?? [],
          inbox: await inboxPromise,
        });
      } catch {
        if (!ac.signal.aborted) setState({ status: "error" });
      }
    })();
    return () => ac.abort();
  }, []);

  const txns = useMemo(
    () => (state.status === "ready" ? state.transactions : []),
    [state],
  );
  const currency = txns[0]?.currency ?? "USD";

  // budgets stay anchored to the latest full month, independent of the picker
  const monthBuckets = useMemo(() => buildBuckets(txns, "month"), [txns]);
  const seriesBuckets = useMemo(
    () => buildBuckets(txns, period, category),
    [txns, period, category],
  );
  const categories = useMemo(() => categoriesPresent(txns), [txns]);

  // the period the detail widgets focus on (defaults to the most recent)
  const effectiveKey = selectedKey || seriesBuckets.at(-1)?.key || "";
  const selectedIdx = seriesBuckets.findIndex((b) => b.key === effectiveKey);
  const selected = selectedIdx >= 0 ? seriesBuckets[selectedIdx] : undefined;
  const prev = selectedIdx > 0 ? seriesBuckets[selectedIdx - 1] : undefined;
  const periods = useMemo(
    () => [...seriesBuckets].reverse().map((b) => ({ key: b.key, fullLabel: b.fullLabel })),
    [seriesBuckets],
  );
  const periodTxns = useMemo(
    () =>
      txns.filter(
        (t) =>
          keyOf(t.date, period) === effectiveKey &&
          (category === "all" || t.category.split(".")[0] === category),
      ),
    [txns, period, effectiveKey, category],
  );

  function changeGranularity(g: Period) {
    setPeriod(g);
    setSelectedKey(""); // snap back to the most recent period at the new granularity
  }

  return (
    <AppShell activeHref="/dashboard">
      <div className="mx-auto w-full max-w-[1400px] px-6 py-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
            <p className="mt-1 text-sm text-[color:var(--color-fg-muted)]">
              Your money at a glance, with what to do next.
            </p>
          </div>
          {state.status === "ready" && txns.length > 0 ? (
            <DashboardFilters
              period={period}
              setPeriod={changeGranularity}
              periods={periods}
              selectedKey={effectiveKey}
              setSelectedKey={setSelectedKey}
              category={category}
              setCategory={setCategory}
              categories={categories}
            />
          ) : null}
        </div>

        {state.status === "loading" ? <DashboardSkeleton /> : null}
        {state.status === "error" ? <Unavailable /> : null}
        {state.status === "ready" ? (
          txns.length === 0 ? (
            <Empty />
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="flex flex-col gap-5"
            >
              <KpiRow selected={selected} prev={prev} granularity={period} currency={currency} />
              <InsightsPanel txns={txns} />
              <div className="grid gap-5 lg:grid-cols-2">
                <TrendChart
                  buckets={seriesBuckets}
                  period={period}
                  currency={currency}
                  selectedKey={effectiveKey}
                  onSelect={setSelectedKey}
                />
                <BudgetProgress monthBuckets={monthBuckets} currency={currency} />
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <CategoryBreakdown byCategory={selected?.byCategory ?? {}} currency={currency} />
                <IncomeExpenses buckets={seriesBuckets} currency={currency} />
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <UpcomingBills currency={currency} />
                <SavingsGoals currency={currency} />
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <LargestPurchases txns={periodTxns} currency={currency} />
                <TransactionsList transactions={periodTxns} />
              </div>
              <Inbox messages={state.inbox} />
            </motion.div>
          )
        ) : null}
      </div>
    </AppShell>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className={`${CARD} h-24`} />
        ))}
      </div>
      <div className={`${CARD} h-28`} />
      <div className="grid gap-5 lg:grid-cols-2">
        <div className={`${CARD} h-64`} />
        <div className={`${CARD} h-64`} />
      </div>
    </div>
  );
}

function Empty() {
  return (
    <div className={`${CARD} p-12 text-center`}>
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)]">
        <Wallet className="h-6 w-6" />
      </div>
      <h2 className="mt-3 text-base font-semibold">No data yet</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-[color:var(--color-fg-muted)]">
        Once transactions load, your dashboard fills in here.
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
    <div className={`${CARD} p-12 text-center`}>
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
