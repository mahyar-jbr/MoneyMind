import type { WeekBucket } from "@/lib/types";
import {
  aggregateCategories,
  formatCategory,
  formatCurrency,
  latestWeek,
  totalSpend,
  weekOverWeek,
} from "@/lib/dashboard";

export function StatCards({
  weeks,
  txCount,
  currency,
}: {
  weeks: WeekBucket[];
  txCount: number;
  currency: string;
}) {
  const total = totalSpend(weeks);
  const latest = latestWeek(weeks);
  const wow = weekOverWeek(weeks);
  const top = aggregateCategories(weeks, 1)[0];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Card
        label="Total spend"
        value={formatCurrency(total, currency, { compact: true })}
        sub={`across ${weeks.length} weeks`}
      />
      <Card
        label="This week"
        value={formatCurrency(
          latest ? Math.abs(latest.total_spend) : 0,
          currency,
          { compact: true },
        )}
        sub={wow != null ? `${wow >= 0 ? "+" : ""}${wow.toFixed(0)}% vs last week` : undefined}
        trend={wow == null ? undefined : wow > 0 ? "up" : wow < 0 ? "down" : undefined}
      />
      <Card
        label="Top category"
        value={top ? formatCategory(top.category) : "None"}
        sub={top ? formatCurrency(top.amount, currency, { compact: true }) : undefined}
      />
      <Card label="Transactions" value={String(txCount)} sub="recent activity" />
    </div>
  );
}

function Card({
  label,
  value,
  sub,
  trend,
}: {
  label: string;
  value: string;
  sub?: string;
  trend?: "up" | "down";
}) {
  const subColor =
    trend === "up"
      ? "text-rose-400"
      : trend === "down"
        ? "text-emerald-400"
        : "text-[color:var(--color-fg-muted)]";

  return (
    <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-[color:var(--color-fg-muted)]">
        {label}
      </p>
      <p className="mt-2 truncate text-2xl font-semibold tracking-tight capitalize">
        {value}
      </p>
      {sub ? <p className={`mt-1 text-xs ${subColor}`}>{sub}</p> : null}
    </div>
  );
}
