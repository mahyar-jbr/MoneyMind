// Display helpers used across the dashboard + chat widgets.
// Aggregation logic lives in lib/analytics.ts (client-side over raw
// transactions). The week-based helpers that used to live here were
// removed 2026-06-08 — the dashboard pivoted to client-side bucketing,
// the old WeekBucket-driven aggregateCategories / totalSpend /
// latestWeek / weekOverWeek were never called after that pivot.

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

// ISO timestamp -> short relative time ("just now", "2h ago", "3d ago"), else a date
export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const min = Math.floor((Date.now() - then) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  if (min < 1440) return `${Math.floor(min / 60)}h ago`;
  if (min < 10080) return `${Math.floor(min / 1440)}d ago`;
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}
