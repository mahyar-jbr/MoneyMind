import type { WeekBucket } from "@/lib/types";
import { formatCurrency, formatWeek } from "@/lib/dashboard";

export function SpendChart({
  weeks,
  currency,
}: {
  weeks: WeekBucket[];
  currency: string;
}) {
  const data = [...weeks].sort((a, b) => a.week.localeCompare(b.week));

  const W = 640;
  const H = 240;
  const padX = 16;
  const padTop = 16;
  const padBottom = 32;
  const innerW = W - padX * 2;
  const innerH = H - padTop - padBottom;
  const max = Math.max(...data.map((w) => Math.abs(w.total_spend)), 1);
  const slot = innerW / Math.max(data.length, 1);
  const barW = Math.min(slot * 0.55, 48);

  return (
    <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40 p-5">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">Weekly spend</h2>
        <span className="text-xs text-[color:var(--color-fg-muted)]">
          peak {formatCurrency(max, currency, { compact: true })}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-56 w-full"
        role="img"
        aria-label={`Weekly spend across ${data.length} weeks`}
      >
        <line
          x1={padX}
          y1={padTop + innerH}
          x2={W - padX}
          y2={padTop + innerH}
          stroke="var(--color-border)"
          strokeWidth="1"
        />
        {data.map((w, i) => {
          const v = Math.abs(w.total_spend);
          const h = (v / max) * innerH;
          const x = padX + slot * i + (slot - barW) / 2;
          const y = padTop + innerH - h;
          const showLabel = data.length <= 10 || i % 2 === 0;
          return (
            <g key={w.week}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={h}
                rx="4"
                style={{ fill: "var(--color-accent)" }}
                className="opacity-80 transition-opacity hover:opacity-100"
              >
                <title>{`${formatWeek(w.week)}: ${formatCurrency(v, currency)}`}</title>
              </rect>
              {showLabel ? (
                <text
                  x={x + barW / 2}
                  y={H - 10}
                  textAnchor="middle"
                  fontSize={10}
                  style={{ fill: "var(--color-fg-muted)" }}
                >
                  {formatWeek(w.week)}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
