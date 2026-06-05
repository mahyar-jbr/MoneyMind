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
      <header className="sticky top-0 z-20 border-b border-white/[0.06] bg-[color:var(--color-bg)]/40 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center justify-between px-6">
          <Link
            href="/"
            className="text-2xl font-semibold tracking-tight text-[color:var(--color-fg)]"
          >
            <span className="text-[color:var(--color-accent)]">Money</span>Mind
          </Link>

          <nav className="flex items-center gap-1.5 text-sm">
            {NAV.map((item) => {
              const active = activeHref === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    active
                      ? "rounded-full bg-white/[0.08] px-3.5 py-1.5 font-medium text-[color:var(--color-fg)]"
                      : "rounded-full px-3.5 py-1.5 font-medium text-[color:var(--color-fg-muted)] transition-colors hover:bg-white/[0.06] hover:text-[color:var(--color-fg)]"
                  }
                >
                  {item.label}
                </Link>
              );
            })}
            <div className="ml-1.5">
              <UserButton />
            </div>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>
    </div>
  );
}
