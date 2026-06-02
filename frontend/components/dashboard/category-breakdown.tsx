import type { WeekBucket } from "@/lib/types";
import { aggregateCategories, formatCategory, formatCurrency } from "@/lib/dashboard";
import { categoryIcon } from "@/lib/categories";

export function CategoryBreakdown({
  weeks,
  currency,
}: {
  weeks: WeekBucket[];
  currency: string;
}) {
  const cats = aggregateCategories(weeks);
  const max = Math.max(...cats.map((c) => c.amount), 1);

  return (
    <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40 p-5">
      <h2 className="mb-4 text-sm font-semibold">Top categories</h2>
      <ul className="flex flex-col gap-3">
        {cats.map((c) => {
          const Icon = categoryIcon(c.category);
          return (
          <li key={c.category}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-[color:var(--color-fg-muted)]" />
                {formatCategory(c.category)}
              </span>
              <span className="text-[color:var(--color-fg-muted)] tabular-nums">
                {formatCurrency(c.amount, currency)}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[color:var(--color-surface-hi)]">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(c.amount / max) * 100}%`,
                  background: "var(--color-accent)",
                }}
              />
            </div>
          </li>
          );
        })}
      </ul>
    </div>
  );
}
