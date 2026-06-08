import { Bell, CalendarRange, Inbox as InboxIcon } from "lucide-react";
import type { InboxMessage } from "@/lib/types";
import { formatRelative } from "@/lib/dashboard";

export function Inbox({ messages }: { messages: InboxMessage[] }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[color:var(--color-surface-hi)]/60 to-[color:var(--color-surface)]/40 shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_24px_60px_-30px_rgba(0,0,0,0.7)] backdrop-blur-xl">
      <h2 className="flex items-center gap-2 border-b border-white/[0.06] px-5 py-4 text-sm font-semibold">
        <InboxIcon className="h-4 w-4 text-[color:var(--color-accent)]" />
        Inbox
      </h2>
      {messages.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-[color:var(--color-fg-muted)]">
          Nothing here yet. Your weekly summary and reminders from MoneyMind show up here.
        </p>
      ) : (
        <ul className="max-h-[380px] divide-y divide-white/[0.06] overflow-y-auto">
          {messages.map((m) => {
            const Icon = m.type === "reminder" ? Bell : CalendarRange;
            return (
              <li key={m.id} className="flex gap-3 px-5 py-4">
                <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)]">
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="truncate text-sm font-medium">{m.title}</p>
                    <span className="shrink-0 text-xs text-[color:var(--color-fg-muted)]">
                      {formatRelative(m.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-[color:var(--color-fg-muted)]">
                    {m.body}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
