"use client";

import { CheckCircle2, FileText, TrendingDown } from "lucide-react";

import { categoryIcon } from "@/lib/categories";
import { formatCurrency } from "@/lib/dashboard";
import type { IngestStatementResponse } from "@/lib/types";


// Demo-aware date formatter: "20 Apr 2026" → "Apr 20" style for the
// period chip in the card header.
function fmtShort(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}


function prettyCategory(topLevel: string): string {
  return topLevel.charAt(0).toUpperCase() + topLevel.slice(1);
}


/**
 * V4 — Statement import card.
 *
 * Rendered in the chat thread after a successful PDF upload. Shows the
 * issuer + period + per-category breakdown so the user (and a judge
 * watching the demo) sees real numbers immediately, without needing to
 * switch to the dashboard.
 *
 * Two card variants:
 *  - `fresh`: just imported, "Saved N transactions" with the breakdown
 *  - `duplicate`: already imported, but we still show the breakdown
 *    (the source-hash dedupe kept the prior import; this surfaces it)
 */
export function StatementCard({
  result,
  filename,
}: {
  result: IngestStatementResponse;
  filename: string;
}) {
  const isDuplicate = result.duplicate_of_prior_upload;
  const periodLabel =
    result.period_start && result.period_end
      ? `${fmtShort(result.period_start)} → ${fmtShort(result.period_end)}`
      : "";

  // Sort categories by descending amount and cap to top 6 — the rest
  // roll into the "+N more" footer.
  const sortedCategories = Object.entries(result.by_category).sort(
    (a, b) => b[1] - a[1],
  );
  const topCategories = sortedCategories.slice(0, 6);
  const remainingCount = sortedCategories.length - topCategories.length;

  return (
    <div className="w-full max-w-md rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[color:var(--color-surface-hi)]/60 to-[color:var(--color-surface)]/40 p-4 shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_24px_60px_-30px_rgba(0,0,0,0.7)] backdrop-blur-xl">
      {/* Header row */}
      <div className="flex items-start gap-3">
        <span
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${
            isDuplicate
              ? "bg-amber-400/10 text-amber-300 ring-1 ring-inset ring-amber-300/20"
              : "bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)] ring-1 ring-inset ring-[color:var(--color-accent)]/20"
          }`}
        >
          {isDuplicate ? (
            <FileText className="h-4 w-4" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
        </span>
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-semibold">
            {isDuplicate ? "Already imported" : "Statement imported"}
          </p>
          <p className="truncate text-xs text-[color:var(--color-fg-muted)]">
            {filename}
            {result.issuer ? ` · ${result.issuer}` : ""}
            {result.account_last4 ? ` ·· ${result.account_last4}` : ""}
          </p>
        </div>
        {periodLabel && (
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[color:var(--color-fg-muted)]">
            {periodLabel}
          </span>
        )}
      </div>

      {/* Total spend hero */}
      <div className="mt-4 flex items-baseline gap-2">
        <p className="text-2xl font-semibold tracking-tight text-[color:var(--color-fg)]">
          {formatCurrency(result.total_spend, "CAD")}
        </p>
        <p className="text-xs text-[color:var(--color-fg-muted)]">
          {isDuplicate ? "previously categorized" : `across ${result.inserted} transactions`}
        </p>
      </div>

      {/* Per-category breakdown */}
      {topCategories.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {topCategories.map(([cat, amount]) => {
            const Icon = categoryIcon(cat);
            const pct =
              result.total_spend > 0 ? (amount / result.total_spend) * 100 : 0;
            return (
              <li key={cat} className="flex items-center gap-3 text-sm">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/[0.04] text-[color:var(--color-fg-muted)]">
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="flex-1 truncate text-[color:var(--color-fg)]">
                  {prettyCategory(cat)}
                </span>
                <span className="tabular-nums text-[color:var(--color-fg-muted)]">
                  {formatCurrency(amount, "CAD", { compact: true })}
                </span>
                <span className="w-10 text-right tabular-nums text-xs text-[color:var(--color-fg-muted)]">
                  {pct.toFixed(0)}%
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {/* Footer */}
      {(remainingCount > 0 ||
        result.payment_count > 0 ||
        result.warnings.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-white/[0.06] pt-2.5 text-xs text-[color:var(--color-fg-muted)]">
          {remainingCount > 0 && <span>+{remainingCount} more categories</span>}
          {result.payment_count > 0 && (
            <span className="inline-flex items-center gap-1">
              <TrendingDown className="h-3 w-3" />
              {result.payment_count} payment{result.payment_count === 1 ? "" : "s"}{" "}
              to card ({formatCurrency(result.payment_total, "CAD", { compact: true })}) — excluded from spending
            </span>
          )}
          {result.warnings.length > 0 && (
            <span className="text-amber-300/80">{result.warnings.join(" · ")}</span>
          )}
        </div>
      )}
    </div>
  );
}
