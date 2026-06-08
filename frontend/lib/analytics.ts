// client-side aggregation over raw transactions. the backend only stores
// transactions, so every spending widget is derived here rather than from a
// dedicated endpoint — keeps the week/month + category filters fully reactive.
import type { Transaction } from "./types";

export type Period = "week" | "month";

export type Bucket = {
  key: string; // sortable: "2026-06-01" (week monday) or "2026-06" (month)
  label: string; // short display: "Jun 1" or "Jun"
  fullLabel: string; // picker display: "Week of Jun 1" or "June 2026"
  spend: number; // outflow, positive
  income: number; // inflow, positive
  byCategory: Record<string, number>; // dotted category -> spend, positive
};

const parse = (d: string): Date => new Date(`${d}T00:00:00Z`);
const topLevel = (category: string): string => category.split(".")[0];

function weekInfo(d: Date): { key: string; label: string; fullLabel: string } {
  const diff = (d.getUTCDay() + 6) % 7; // days since monday
  const monday = new Date(d);
  monday.setUTCDate(d.getUTCDate() - diff);
  const short = monday.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
  return {
    key: monday.toISOString().slice(0, 10),
    label: short,
    fullLabel: `Week of ${short}`,
  };
}

function monthInfo(d: Date): { key: string; label: string; fullLabel: string } {
  return {
    key: `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`,
    label: d.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" }),
    fullLabel: d.toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }),
  };
}

// the bucket key a transaction falls into, for filtering txns to a period
export function keyOf(dateStr: string, period: Period): string {
  const d = parse(dateStr);
  return period === "week" ? weekInfo(d).key : monthInfo(d).key;
}

export function buildBuckets(
  txns: Transaction[],
  period: Period,
  categoryFilter?: string,
): Bucket[] {
  const map = new Map<string, Bucket>();
  const hasCategoryFilter = !!categoryFilter && categoryFilter !== "all";
  for (const t of txns) {
    const isInflow = t.amount > 0;
    // Apply categoryFilter ONLY to outflows. Income (inflow) has its own
    // category namespace ("income.salary" etc.) so filtering by "food" or
    // "shopping" would zero out every salary deposit and silently break the
    // IncomeExpenses chart + the savings-rate KPI whenever the user picks
    // a spend category.
    if (hasCategoryFilter && !isInflow && topLevel(t.category) !== categoryFilter) {
      continue;
    }
    const { key, label, fullLabel } =
      period === "week" ? weekInfo(parse(t.date)) : monthInfo(parse(t.date));
    let b = map.get(key);
    if (!b) {
      b = { key, label, fullLabel, spend: 0, income: 0, byCategory: {} };
      map.set(key, b);
    }
    if (isInflow) {
      b.income += t.amount;
    } else {
      const amt = -t.amount;
      b.spend += amt;
      b.byCategory[t.category] = (b.byCategory[t.category] ?? 0) + amt;
    }
  }
  return [...map.values()].sort((a, b) => a.key.localeCompare(b.key));
}

export type CategoryTotal = { category: string; amount: number };

export function rankCategories(
  byCategory: Record<string, number>,
  top = 6,
): CategoryTotal[] {
  const sorted = Object.entries(byCategory)
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount);
  if (sorted.length <= top) return sorted;
  const head = sorted.slice(0, top);
  const other = sorted.slice(top).reduce((s, c) => s + c.amount, 0);
  return other > 0 ? [...head, { category: "Other", amount: other }] : head;
}

// top-level category spend across all txns, biggest first
export function topLevelSpend(txns: Transaction[]): CategoryTotal[] {
  const map: Record<string, number> = {};
  for (const t of txns) {
    if (t.amount < 0) {
      const k = topLevel(t.category);
      map[k] = (map[k] ?? 0) + -t.amount;
    }
  }
  return Object.entries(map)
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount);
}

export function categoriesPresent(txns: Transaction[]): string[] {
  const set = new Set<string>();
  for (const t of txns) if (t.amount < 0) set.add(topLevel(t.category));
  return [...set].sort();
}

export const pctChange = (curr: number, prev: number): number | null =>
  prev === 0 ? null : ((curr - prev) / prev) * 100;

// savings rate over the latest bucket that has income
export function savingsRate(buckets: Bucket[]): number | null {
  for (let i = buckets.length - 1; i >= 0; i--) {
    if (buckets[i].income > 0) {
      return ((buckets[i].income - buckets[i].spend) / buckets[i].income) * 100;
    }
  }
  return null;
}

export type Largest = {
  merchant: string;
  category: string;
  amount: number;
  date: string;
};

export function largestPurchases(txns: Transaction[], n = 5): Largest[] {
  return txns
    .filter((t) => t.amount < 0)
    .sort((a, b) => a.amount - b.amount)
    .slice(0, n)
    .map((t) => ({
      merchant: t.merchant || t.merchant_canonical,
      category: t.category,
      amount: -t.amount,
      date: t.date,
    }));
}

export type Insight = { tone: "warn" | "good" | "info"; text: string };

// a small set of decision-oriented insights, computed from real data
export function deriveInsights(txns: Transaction[]): Insight[] {
  const months = buildBuckets(txns, "month");
  if (months.length === 0) return [];
  const curr = months[months.length - 1];
  const prev = months.length > 1 ? months[months.length - 2] : null;
  const out: Insight[] = [];

  if (prev) {
    const change = pctChange(curr.spend, prev.spend);
    if (change != null && Math.abs(change) >= 3) {
      out.push(
        change > 0
          ? { tone: "warn", text: `Spending is up ${change.toFixed(0)}% vs last month.` }
          : { tone: "good", text: `Nice, spending is down ${Math.abs(change).toFixed(0)}% vs last month.` },
      );
    }

    // category with the biggest month-over-month jump
    let topCat = "";
    let topJump = 0;
    for (const [cat, amt] of Object.entries(curr.byCategory)) {
      const change = pctChange(amt, prev.byCategory[cat] ?? 0);
      if (change != null && change > topJump && amt > 20) {
        topJump = change;
        topCat = cat;
      }
    }
    if (topCat) {
      out.push({
        tone: "warn",
        text: `${labelCategory(topCat)} is up ${topJump.toFixed(0)}% this month.`,
      });
    }
  }

  // biggest category this month, share of spend
  const ranked = rankCategories(curr.byCategory, 1)[0];
  if (ranked && curr.spend > 0) {
    const share = (ranked.amount / curr.spend) * 100;
    out.push({
      tone: "info",
      text: `${labelCategory(ranked.category)} is your top category, ${share.toFixed(0)}% of this month's spend.`,
    });
  }

  // projected month-end spend, by pace — only fires when curr is actually
  // the current calendar month. Otherwise we'd be projecting "this month"
  // off a stale bucket (e.g. May synthetic data on a June clock → "you'll
  // spend $14k this month"), which reads as broken on camera.
  if (curr.spend > 0) {
    const now = new Date();
    const currentKey = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
    if (curr.key === currentKey) {
      const day = now.getUTCDate();
      const daysInMonth = new Date(
        Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0),
      ).getUTCDate();
      if (day >= 3 && day < daysInMonth) {
        const projected = (curr.spend / day) * daysInMonth;
        out.push({
          tone: "info",
          text: `At this pace you'll spend about $${Math.round(projected).toLocaleString()} this month.`,
        });
      }
    }
  }

  return out.slice(0, 4);
}

// "food.delivery" -> "Delivery" for inline use in insight sentences
function labelCategory(category: string): string {
  const part = category.includes(".")
    ? category.split(".").slice(1).join(" ")
    : category;
  const clean = part.replace(/_/g, " ");
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}
