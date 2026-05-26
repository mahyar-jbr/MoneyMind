import Link from "next/link";
import { UserButton } from "@clerk/nextjs";

const NAV = [
  { href: "/chat", label: "Chat" },
  { href: "/dashboard", label: "Dashboard" },
];

export function AppShell({
  children,
  activeHref,
}: {
  children: React.ReactNode;
  activeHref?: string;
}) {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-10 border-b border-[color:var(--color-border)] bg-[color:var(--color-bg)]/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-emerald-400 to-emerald-600 text-sm font-bold text-zinc-950">
              M
            </span>
            <span className="font-semibold tracking-tight">MoneyMind</span>
          </Link>

          <nav className="flex items-center gap-1 text-sm">
            {NAV.map((item) => {
              const active = activeHref === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    active
                      ? "rounded-full bg-[color:var(--color-surface-hi)] px-3 py-1.5 font-medium text-foreground"
                      : "rounded-full px-3 py-1.5 font-medium text-[color:var(--color-fg-muted)] hover:bg-[color:var(--color-surface)] hover:text-foreground"
                  }
                >
                  {item.label}
                </Link>
              );
            })}
            <div className="ml-2">
              <UserButton />
            </div>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>
    </div>
  );
}
