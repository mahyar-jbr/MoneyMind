import type { WeekBucket } from "./types";

export type CategoryTotal = { category: string; amount: number };

// sum each category across all weeks, biggest first, rest rolled into "Other"
export function aggregateCategories(
  weeks: WeekBucket[],
  top = 6,
): CategoryTotal[] {
  const totals = new Map<string, number>();
  for (const w of weeks) {
    for (const [cat, amt] of Object.entries(w.by_category)) {
      totals.set(cat, (totals.get(cat) ?? 0) + Math.abs(amt));
    }
  }

  const sorted = [...totals.entries()]
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount);

  if (sorted.length <= top) return sorted;
  const head = sorted.slice(0, top);
  const other = sorted.slice(top).reduce((sum, c) => sum + c.amount, 0);
  return other > 0 ? [...head, { category: "Other", amount: other }] : head;
}

export function totalSpend(weeks: WeekBucket[]): number {
  return weeks.reduce((sum, w) => sum + Math.abs(w.total_spend), 0);
}

function byWeekAsc(weeks: WeekBucket[]): WeekBucket[] {
  return [...weeks].sort((a, b) => a.week.localeCompare(b.week));
}

export function latestWeek(weeks: WeekBucket[]): WeekBucket | null {
  if (weeks.length === 0) return null;
  return byWeekAsc(weeks).at(-1) ?? null;
}

// percent change of the latest week vs the previous one, null if not enough data
export function weekOverWeek(weeks: WeekBucket[]): number | null {
  if (weeks.length < 2) return null;
  const sorted = byWeekAsc(weeks);
  const prev = Math.abs(sorted[sorted.length - 2].total_spend);
  const curr = Math.abs(sorted[sorted.length - 1].total_spend);
  if (prev === 0) return null;
  return ((curr - prev) / prev) * 100;
}

export function formatCurrency(
  amount: number,
  currency = "USD",
  opts?: { compact?: boolean },
): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: opts?.compact ? 0 : 2,
  }).format(amount);
}

// "2026-05-04" -> "May 4"
//
// Parse and format in UTC: the wire format is a plain ISO date string
// (no time, no zone) produced by Python `.date().isoformat()` in the
// backend. Interpreting it in the browser's local timezone caused a
// one-day drift on screen for users in negative-UTC offsets — #21a.
// See docs/architecture.md § "Week semantics".
export function formatWeek(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

// "2026-05-04" -> "May 4, 2026"
export function formatDate(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

// "food.delivery" -> "Delivery", "savings.emergency_fund" -> "Emergency fund"
export function formatCategory(category: string): string {
  const part = category.includes(".")
    ? category.split(".").slice(1).join(" ")
    : category;
  const clean = part.replace(/_/g, " ");
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}
