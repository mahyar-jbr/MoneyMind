import Link from "next/link";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b border-[color:var(--color-border)] bg-[color:var(--color-bg)]/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <Logo />
            <span className="font-semibold tracking-tight">MoneyMind</span>
          </Link>

          <div className="flex items-center gap-3 text-sm">
            <SignedOut>
              <SignInButton mode="modal">
                <button className="rounded-full bg-[color:var(--color-accent)] px-4 py-1.5 font-medium text-zinc-950 transition-colors hover:bg-[color:var(--color-accent-hi)]">
                  Sign in
                </button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <Link
                href="/dashboard"
                className="rounded-full bg-[color:var(--color-surface-hi)] px-4 py-1.5 font-medium hover:bg-zinc-700"
              >
                Open dashboard
              </Link>
              <UserButton />
            </SignedIn>
          </div>
        </div>
      </header>

      <main className="flex flex-1 items-center">
        <div className="mx-auto w-full max-w-6xl px-6 py-24">
          <div className="flex max-w-3xl flex-col gap-6">
            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
              An AI co-pilot that{" "}
              <span className="bg-gradient-to-r from-emerald-300 to-teal-400 bg-clip-text text-transparent">
                remembers who you are
              </span>{" "}
              with money.
            </h1>

            <p className="max-w-2xl text-lg leading-relaxed text-[color:var(--color-fg-muted)]">
              Every finance app remembers your transactions. MoneyMind remembers
              you — your patterns, your stated context, your goals, and how
              you&apos;ve responded to past nudges.
            </p>

            <div className="flex flex-wrap gap-3">
              <SignedOut>
                <SignInButton mode="modal">
                  <button className="inline-flex h-11 items-center justify-center rounded-full bg-[color:var(--color-accent)] px-6 text-sm font-semibold text-zinc-950 transition-colors hover:bg-[color:var(--color-accent-hi)]">
                    Get started
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <Link
                  href="/chat"
                  className="inline-flex h-11 items-center justify-center rounded-full bg-[color:var(--color-accent)] px-6 text-sm font-semibold text-zinc-950 transition-colors hover:bg-[color:var(--color-accent-hi)]"
                >
                  Open chat
                </Link>
              </SignedIn>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function Logo() {
  return (
    <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-emerald-400 to-emerald-600 text-sm font-bold text-zinc-950 shadow-sm">
      M
    </span>
  );
}
