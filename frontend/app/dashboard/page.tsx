import Link from "next/link";
import { Wallet } from "lucide-react";
import { AppShell } from "@/components/app-shell";

// TODO: charts + goals — Sprint 2 #23
export default function DashboardPage() {
  return (
    <AppShell activeHref="/dashboard">
      <div className="mx-auto w-full max-w-6xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-[color:var(--color-fg-muted)]">
            Nothing here yet.
          </p>
        </div>

        <div className="rounded-2xl border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)]/40 p-12 text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)]">
            <Wallet className="h-6 w-6" />
          </div>
          <h2 className="mt-3 text-base font-semibold">No data yet</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-[color:var(--color-fg-muted)]">
            Once transactions load, spending and goals show up here.
          </p>
          <Link
            href="/chat"
            className="mt-4 inline-flex h-10 items-center justify-center rounded-full bg-[color:var(--color-accent)] px-5 text-sm font-semibold text-zinc-950 hover:bg-[color:var(--color-accent-hi)]"
          >
            Try the chat
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
