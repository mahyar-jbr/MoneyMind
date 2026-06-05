"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import { ArrowRight, Bell, Sparkles } from "lucide-react";

const rise = (delay: number) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay, ease: "easeOut" as const },
});

export default function Home() {
  return (
    <div className="relative isolate flex min-h-svh flex-col overflow-hidden">
      {/* ambient glow */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-48 left-1/2 h-[620px] w-[1000px] -translate-x-1/2 rounded-full bg-[color:var(--color-accent)]/12 blur-[140px]" />
        <div className="absolute right-0 top-1/4 hidden h-[560px] w-[640px] translate-x-1/4 rounded-full bg-[color:var(--color-accent)]/[0.07] blur-[130px] lg:block" />
      </div>

      {/* Spline 3D background (prototype, preview only, not committed) */}
      {/* iframe scaled to 120% + centered so the corner "Built with Spline" badge is clipped by overflow-hidden */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <iframe
          src="https://my.spline.design/bitcoincoins-wiXPOmu1Rpb4g8dvF2V9JtBz/"
          title="3D background"
          className="absolute left-1/2 top-1/2 h-[120%] w-[120%] -translate-x-1/2 -translate-y-1/2 border-0"
        />
      </div>

      <header className="border-b border-white/[0.06] bg-[color:var(--color-bg)]/40 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center justify-between px-6">
          <Link
            href="/"
            className="text-2xl font-semibold tracking-tight text-[color:var(--color-fg)]"
          >
            <span className="text-[color:var(--color-accent)]">Money</span>Mind
          </Link>

          <nav className="flex items-center gap-1.5 text-sm">
            <SignedOut>
              <SignInButton mode="modal">
                <button className="rounded-full border border-white/10 bg-white/[0.05] px-4 py-1.5 font-medium text-[color:var(--color-fg)] transition-colors hover:bg-white/[0.1]">
                  Sign in
                </button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <Link
                href="/dashboard"
                className="rounded-full px-3.5 py-1.5 font-medium text-[color:var(--color-fg-muted)] transition-colors hover:bg-white/[0.06] hover:text-[color:var(--color-fg)]"
              >
                Dashboard
              </Link>
              <UserButton />
            </SignedIn>
          </nav>
        </div>
      </header>

      <main className="flex flex-1 items-center">
        <div className="mx-auto grid w-full max-w-[1600px] grid-cols-1 items-center gap-x-12 gap-y-16 px-6 py-20 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="flex max-w-2xl flex-col items-start gap-6">
            <motion.h1
              {...rise(0.08)}
              className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl"
            >
              An AI co-pilot that{" "}
              <span className="bg-gradient-to-r from-emerald-300 to-teal-400 bg-clip-text text-transparent">
                remembers who you are
              </span>{" "}
              with money.
            </motion.h1>

            <motion.p
              {...rise(0.16)}
              className="max-w-2xl text-lg leading-relaxed text-[color:var(--color-fg-muted)]"
            >
              Every finance app remembers your transactions. MoneyMind remembers
              you: your patterns, your stated context, your goals, and how you
              have responded to past nudges.
            </motion.p>

            <motion.div
              {...rise(0.24)}
              className="mt-2 flex flex-wrap items-center gap-3"
            >
              <SignedOut>
                <SignInButton mode="modal">
                  <button className="group inline-flex h-11 items-center justify-center gap-1.5 rounded-full bg-[color:var(--color-accent)] px-6 text-sm font-semibold text-zinc-950 shadow-[0_10px_40px_-10px_rgba(52,211,153,0.55)] transition-colors hover:bg-[color:var(--color-accent-hi)]">
                    Get started
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <Link
                  href="/chat"
                  className="group inline-flex h-11 items-center justify-center gap-1.5 rounded-full bg-[color:var(--color-accent)] px-6 text-sm font-semibold text-zinc-950 shadow-[0_10px_40px_-10px_rgba(52,211,153,0.55)] transition-colors hover:bg-[color:var(--color-accent-hi)]"
                >
                  Open chat
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </Link>
                <Link
                  href="/dashboard"
                  className="inline-flex h-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.02] px-6 text-sm font-medium text-[color:var(--color-fg-muted)] transition-colors hover:bg-white/[0.06] hover:text-[color:var(--color-fg)]"
                >
                  View dashboard
                </Link>
              </SignedIn>
            </motion.div>
          </div>

          <HeroPreview />
        </div>
      </main>

      <footer className="border-t border-white/5">
        <div className="mx-auto flex w-full max-w-[1600px] flex-col items-center justify-between gap-4 px-6 py-8 text-center sm:flex-row sm:text-left">
          <p className="text-xs text-[color:var(--color-fg-muted)]">
            Built on Gemini and MongoDB Atlas.
          </p>
          <a
            href="https://github.com/mahyar-jbr/MoneyMind"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-[color:var(--color-fg-muted)] transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-[color:var(--color-fg)]"
          >
            <GitHubIcon className="h-4 w-4" />
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}

function HeroPreview() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.7, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className="relative mx-auto w-full max-w-md lg:mx-0 lg:ml-auto"
    >
      {/* halo behind the preview */}
      <div className="pointer-events-none absolute -inset-10 -z-10">
        <div className="absolute inset-0 rounded-[48px] bg-[color:var(--color-accent)]/[0.08] blur-3xl" />
      </div>

      <motion.div
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
        className="relative"
      >
        {/* offset panel for depth */}
        <div
          aria-hidden
          className="absolute -right-3 -top-3 h-full w-full rounded-3xl border border-white/[0.06] bg-[color:var(--color-surface)]/15"
        />

        {/* chat panel */}
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-[color:var(--color-surface-hi)]/80 to-[color:var(--color-surface)]/70 shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_30px_80px_-30px_rgba(0,0,0,0.9)] backdrop-blur-xl">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--color-accent)]/50 to-transparent" />

          {/* header */}
          <div className="flex items-center gap-2.5 border-b border-white/[0.06] px-5 py-3.5">
            <span className="text-sm font-semibold tracking-tight">
              MoneyMind
            </span>
            <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-[color:var(--color-fg-muted)]">
              <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--color-accent)]" />
              online
            </span>
          </div>

          {/* thread: live, self-playing demo */}
          <div className="p-5">
            <HeroChatDemo />
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

function PreviewBubble({
  role,
  children,
}: {
  role: "user" | "assistant";
  children: ReactNode;
}) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-[13px] leading-6 ${
          isUser
            ? "rounded-br-md bg-[color:var(--color-accent)] text-zinc-950"
            : "rounded-bl-md border border-[color:var(--color-border)] bg-[color:var(--color-surface)] text-[color:var(--color-fg)]"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

type Msg =
  | { from: "user"; text: string }
  | { from: "ai"; text: string }
  | { from: "nudge"; title: string; body: string };

const EXAMPLES: Msg[][] = [
  [
    {
      from: "ai",
      text: "Heads up: you're at $310 on dining this week, above your usual ~$200.",
    },
    { from: "user", text: "Can I still do sushi tonight?" },
    {
      from: "ai",
      text: "You've got about $90 of buffer left, so sushi works if you keep it under ~$35.",
    },
    {
      from: "nudge",
      title: "Remind you to cook this Friday at 6pm?",
      body: "You usually order delivery then, so a nudge could save you ~$40.",
    },
  ],
  [
    { from: "user", text: "How's my spending this month?" },
    {
      from: "ai",
      text: "You're 12% under budget. One pattern though: Friday delivery is up, 4 orders vs your usual 2.",
    },
    { from: "user", text: "Anything I should do?" },
    {
      from: "nudge",
      title: "Set a $250 dining cap this month?",
      body: "You're trending toward ~$340 at this pace.",
    },
  ],
  [
    { from: "user", text: "Am I on track for the Japan trip?" },
    {
      from: "ai",
      text: "You've saved $1,840 of $3,000, right on pace for October.",
    },
    {
      from: "ai",
      text: "Skip two delivery nights a week and you'd get there about 3 weeks early.",
    },
    {
      from: "nudge",
      title: "Auto-move $50 to the trip fund each Friday?",
      body: "Matches your current saving pace.",
    },
  ],
];

function HeroChatDemo() {
  const [exIdx, setExIdx] = useState(0);
  const [step, setStep] = useState(0);
  const [streamed, setStreamed] = useState("");
  const [typing, setTyping] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

    async function run() {
      await sleep(600);
      let ex = 0;
      while (!cancelled) {
        setExIdx(ex);
        setStep(0);
        setStreamed("");
        setTyping(false);
        await sleep(450);
        if (cancelled) return;

        const example = EXAMPLES[ex];
        for (let s = 0; s < example.length; s++) {
          if (cancelled) return;
          setStep(s);
          setStreamed("");
          const msg = example[s];
          if (msg.from === "ai") {
            setTyping(true);
            await sleep(850);
            if (cancelled) return;
            setTyping(false);
            const words = msg.text.split(" ");
            for (let w = 0; w < words.length; w++) {
              if (cancelled) return;
              setStreamed(words.slice(0, w + 1).join(" "));
              await sleep(45);
            }
            await sleep(550);
          } else {
            setTyping(false);
            await sleep(msg.from === "nudge" ? 850 : 750);
          }
        }

        // hold the finished example for ~10s, then move on
        await sleep(10000);
        if (cancelled) return;
        ex = (ex + 1) % EXAMPLES.length;
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  const example = EXAMPLES[exIdx];

  return (
    <div className="h-[384px]">
      <AnimatePresence mode="wait">
        <motion.div
          key={exIdx}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col gap-3"
        >
          {example.slice(0, step + 1).map((msg, i) => {
            const isCurrent = i === step;
            if (msg.from === "nudge") {
              return <NudgeCard key={i} title={msg.title} body={msg.body} />;
            }
            const isAi = msg.from === "ai";
            // don't show the current AI bubble until it starts thinking/streaming
            if (isCurrent && isAi && !typing && !streamed) return null;
            const text = isCurrent && isAi ? streamed : msg.text;
            const showTyping = isCurrent && isAi && typing;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
              >
                <PreviewBubble role={isAi ? "assistant" : "user"}>
                  {showTyping ? <TypingDots /> : text}
                </PreviewBubble>
              </motion.div>
            );
          })}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-[color:var(--color-fg-muted)]"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: i * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </span>
  );
}

function NudgeCard({ title, body }: { title: string; body: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-[color:var(--color-bg)]/60 p-4"
    >
      <div className="mb-2.5 inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
        <Sparkles className="h-3 w-3" />
        Suggested
      </div>
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)] ring-1 ring-inset ring-[color:var(--color-accent)]/20">
          <Bell className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold tracking-tight text-[color:var(--color-fg)]">
            {title}
          </p>
          <p className="mt-0.5 text-[13px] leading-relaxed text-[color:var(--color-fg-muted)]">
            {body}
          </p>
          <div className="mt-3 flex gap-2">
            <span className="rounded-lg bg-[color:var(--color-accent)] px-3 py-1.5 text-xs font-semibold text-zinc-950">
              Sounds good
            </span>
            <span className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-1.5 text-xs text-[color:var(--color-fg-muted)]">
              Not now
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  );
}