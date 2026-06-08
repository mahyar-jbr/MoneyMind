import type { Transaction } from "@/lib/types";
import { formatCategory, formatCurrency, formatDate } from "@/lib/dashboard";
import { categoryIcon } from "@/lib/categories";

export function TransactionsList({
  transactions,
}: {
  transactions: Transaction[];
}) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[color:var(--color-surface-hi)]/60 to-[color:var(--color-surface)]/40 shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_24px_60px_-30px_rgba(0,0,0,0.7)] backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
        <h2 className="text-sm font-semibold">Recent transactions</h2>
        <span className="text-xs tabular-nums text-[color:var(--color-fg-muted)]">
          {transactions.length}
        </span>
      </div>
      <ul className="max-h-[380px] divide-y divide-white/[0.06] overflow-y-auto">
        {transactions.map((t, i) => {
          const name = t.merchant || t.merchant_canonical;
          const spend = t.amount < 0;
          const Icon = categoryIcon(t.category);
          return (
            <li
              key={`${t.date}-${name}-${i}`}
              className="flex items-center gap-3 px-5 py-3"
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[color:var(--color-surface-hi)] text-[color:var(--color-fg-muted)]">
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{name}</p>
                <p className="mt-0.5 text-xs text-[color:var(--color-fg-muted)]">
                  <span>{formatCategory(t.category)}</span> · {formatDate(t.date)}
                </p>
              </div>
              <span
                className={
                  spend
                    ? "shrink-0 text-sm tabular-nums text-rose-300"
                    : "shrink-0 text-sm tabular-nums text-emerald-400"
                }
              >
                {formatCurrency(t.amount, t.currency)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
