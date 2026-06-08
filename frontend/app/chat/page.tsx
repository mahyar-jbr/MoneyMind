"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Loader2,
  PieChart,
  PiggyBank,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { streamChat } from "@/lib/chat-stream";
import { InterventionCard } from "@/components/chat/intervention-card";
import type { Intervention, InterventionResponse } from "@/lib/interventions";
import {
  fetchPendingInterventions,
  respondToIntervention,
} from "@/lib/interventions";

type Role = "user" | "assistant";
type ContentMessage = { id: string; role: Role; content: string };
type InterventionItem = {
  id: string;
  kind: "intervention";
  intervention: Intervention;
};
type Message = ContentMessage | InterventionItem;

const SUGGESTIONS: { text: string; icon: LucideIcon }[] = [
  { text: "How can you help me?", icon: Sparkles },
  { text: "Show me this month's spending", icon: TrendingUp },
  { text: "Where is my money going?", icon: PieChart },
  { text: "Help me save money", icon: PiggyBank },
];

const WELCOME: ContentMessage = {
  id: "welcome",
  role: "assistant",
  content: "Hi, I'm MoneyMind. What's on your mind?",
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, streaming]);

  // NOTE: previously we had an unmount cleanup that called
  // abortRef.current?.abort(). Removed because it was canceling in-flight
  // requests in prod when React's effect lifecycle fired the cleanup mid-
  // stream, visible in DevTools as the chat request going to "(canceled)"
  // around 1.8s. Users can refresh to abort; we don't need fancier UX.

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const userMsg: ContentMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    const assistantId = crypto.randomUUID();
    const assistantMsg: ContentMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
    };

    const next = [...messages, userMsg, assistantMsg];
    setMessages(next);
    setInput("");
    setStreaming(true);

    abortRef.current = new AbortController();
    try {
      const turn = [...messages, userMsg]
        .filter((m): m is ContentMessage => !("kind" in m))
        .map(({ role, content }) => ({ role, content }));
      for await (const chunk of streamChat(turn, abortRef.current.signal)) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && !("kind" in m)
              ? { ...m, content: m.content + chunk }
              : m,
          ),
        );
      }
      // after each reply, surface any interventions the agent proposed.
      // Dedup against what we've already rendered, since the backend keeps a
      // pending intervention in the list until the user accepts/declines,
      // so without this it would re-append on every turn.
      const pending = await fetchPendingInterventions();
      if (pending.length) {
        setMessages((prev) => {
          const seen = new Set(
            prev
              .filter((m): m is InterventionItem => "kind" in m)
              .map((m) => m.intervention.intervention_id),
          );
          const fresh = pending.filter((it) => !seen.has(it.intervention_id));
          if (!fresh.length) return prev;
          return [
            ...prev,
            ...fresh.map((it) => ({
              id: it.intervention_id,
              kind: "intervention" as const,
              intervention: it,
            })),
          ];
        });
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && !("kind" in m)
            ? {
                ...m,
                content:
                  m.content + "\n\n(Connection lost. Try again in a moment.)",
              }
            : m,
        ),
      );
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    send(input);
  }

  async function respondTo(
    itemId: string,
    interventionId: string,
    response: InterventionResponse,
    modifiedParams?: Record<string, string>,
  ) {
    await respondToIntervention(interventionId, response, modifiedParams);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === itemId && "kind" in m
          ? {
              ...m,
              intervention: {
                ...m.intervention,
                status: response === "ignored" ? "ignored" : "responded",
                user_response: response,
                params: modifiedParams
                  ? { ...m.intervention.params, ...modifiedParams }
                  : m.intervention.params,
              },
            }
          : m,
      ),
    );
  }

  return (
    <AppShell activeHref="/chat" glow={false}>
      <div className="mx-auto flex h-[calc(100svh-4rem)] w-full max-w-3xl flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
          <div className="flex flex-col gap-4">
            {messages.map((m) =>
              "kind" in m ? (
                <div key={m.id} className="flex justify-start">
                  <InterventionCard
                    intervention={m.intervention}
                    onRespond={(response, modifiedParams) =>
                      respondTo(
                        m.id,
                        m.intervention.intervention_id,
                        response,
                        modifiedParams,
                      )
                    }
                  />
                </div>
              ) : (
                <Bubble key={m.id} message={m} />
              ),
            )}
            {messages.length === 1 && (
              <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.text}
                    type="button"
                    onClick={() => send(s.text)}
                    disabled={streaming}
                    className="group flex items-center gap-3 rounded-2xl border border-white/[0.08] bg-[color:var(--color-surface)]/50 px-4 py-3.5 text-left backdrop-blur-sm transition-colors hover:border-[color:var(--color-accent)]/40 hover:bg-[color:var(--color-surface-hi)]/60 disabled:opacity-50"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)] ring-1 ring-inset ring-[color:var(--color-accent)]/20">
                      <s.icon className="h-4 w-4" />
                    </span>
                    <span className="text-sm font-medium text-[color:var(--color-fg-muted)] transition-colors group-hover:text-[color:var(--color-fg)]">
                      {s.text}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-white/[0.06] bg-[color:var(--color-bg)]/60 backdrop-blur-xl">
          <form
            onSubmit={onSubmit}
            className="mx-auto flex w-full items-end gap-2 px-4 py-3"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Tell MoneyMind what's going on…"
              rows={1}
              disabled={streaming}
              className="max-h-40 min-h-[44px] flex-1 resize-none rounded-2xl border border-white/[0.08] bg-[color:var(--color-surface)]/60 px-4 py-2.5 text-sm leading-6 outline-none backdrop-blur-xl transition-colors placeholder:text-zinc-500 focus:border-[color:var(--color-accent)] focus:ring-2 focus:ring-[color:var(--color-accent)]/20 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!input.trim() || streaming}
              className="grid h-11 w-11 place-items-center rounded-full bg-[color:var(--color-accent)] text-zinc-950 transition-colors hover:bg-[color:var(--color-accent-hi)] disabled:cursor-not-allowed disabled:bg-[color:var(--color-surface-hi)] disabled:text-[color:var(--color-fg-muted)]"
              aria-label={streaming ? "Sending" : "Send"}
            >
              {streaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowUp className="h-4 w-4" />
              )}
            </button>
          </form>
        </div>
      </div>
    </AppShell>
  );
}

function Bubble({ message }: { message: ContentMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-6 ${
          isUser
            ? "rounded-br-md bg-[color:var(--color-accent)] text-zinc-950"
            : "rounded-bl-md border border-white/[0.08] bg-[color:var(--color-surface)]/60 text-foreground backdrop-blur-xl"
        }`}
      >
        {message.content || (
          <span className="text-[color:var(--color-fg-muted)]">...</span>
        )}
      </div>
    </div>
  );
}
