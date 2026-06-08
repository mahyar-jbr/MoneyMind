"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Loader2,
  Paperclip,
  PieChart,
  PiggyBank,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { streamChat } from "@/lib/chat-stream";
import { InterventionCard } from "@/components/chat/intervention-card";
import { StatementCard } from "@/components/chat/statement-card";
import { ImportProgress } from "@/components/chat/import-progress";
import type { Intervention, InterventionResponse } from "@/lib/interventions";
import {
  fetchPendingInterventions,
  respondToIntervention,
} from "@/lib/interventions";
import { uploadStatement } from "@/lib/api";
import type { IngestProgressEvent } from "@/lib/api";
import type { IngestStatementResponse } from "@/lib/types";

type Role = "user" | "assistant";
type ContentMessage = { id: string; role: Role; content: string };
type InterventionItem = {
  id: string;
  kind: "intervention";
  intervention: Intervention;
};
type StatementItem = {
  id: string;
  kind: "statement";
  filename: string;
  result: IngestStatementResponse;
};
// Live progress timeline. While the upload is in-flight this morphs as
// SSE events arrive; on `done` the parent swaps it for a StatementItem.
type ImportProgressItem = {
  id: string;
  kind: "import-progress";
  filename: string;
  events: IngestProgressEvent[];
  startedAt: number;
  elapsedMs: number;
  errorMessage?: string;
};
type Message =
  | ContentMessage
  | InterventionItem
  | StatementItem
  | ImportProgressItem;

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
  const [uploading, setUploading] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
        .filter((m): m is ContentMessage => !("kind" in m))  // skip intervention + statement cards
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
              .filter((m): m is InterventionItem => "kind" in m && m.kind === "intervention")
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
        m.id === itemId && "kind" in m && m.kind === "intervention"
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

  async function handleFileUpload(file: File) {
    if (uploading || streaming) return;

    // Sanity check on extension/MIME before we burn an upload round-trip.
    const isPdf =
      file.name.toLowerCase().endsWith(".pdf") ||
      file.type === "application/pdf";
    if (!isPdf) {
      const errMsg: ContentMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `That doesn't look like a PDF (${file.name}). Drop a bank-statement PDF and I'll read it.`,
      };
      setMessages((m) => [...m, errMsg]);
      return;
    }

    // Surface the upload as a user bubble so the conversation reads
    // naturally ("📎 Uploaded x.pdf" → live progress timeline → card).
    const userMsg: ContentMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: `📎 Uploaded ${file.name}`,
    };
    const progressId = crypto.randomUUID();
    const startedAt = Date.now();
    const initialProgress: ImportProgressItem = {
      id: progressId,
      kind: "import-progress",
      filename: file.name,
      events: [],
      startedAt,
      elapsedMs: 0,
    };
    setMessages((m) => [...m, userMsg, initialProgress]);
    setUploading(true);

    // Tick elapsedMs every 250ms while the upload is live so the chip
    // in the progress card updates and the user can SEE time passing
    // (more reassuring than a frozen timer when Gemini takes 10s).
    const tickHandle = window.setInterval(() => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === progressId && "kind" in m && m.kind === "import-progress"
            ? { ...m, elapsedMs: Date.now() - startedAt }
            : m,
        ),
      );
    }, 250);

    try {
      const result = await uploadStatement(file, {
        onProgress: (event) => {
          // Append the event to the progress item's events list.
          setMessages((prev) =>
            prev.map((m) =>
              m.id === progressId && "kind" in m && m.kind === "import-progress"
                ? { ...m, events: [...m.events, event] }
                : m,
            ),
          );
        },
      });

      window.clearInterval(tickHandle);

      // Swap the progress item for a final summary bubble + StatementCard.
      const summary = result.duplicate_of_prior_upload
        ? `This statement was already imported. Here's the breakdown I have on file.`
        : `Imported ${result.inserted} transactions from your ${result.issuer || "statement"} (${result.period_start ?? ""} → ${result.period_end ?? ""}). Total spend ${formatTotal(result.total_spend)}. Check your dashboard for the bars.`;
      const summaryMsg: ContentMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: summary,
      };
      const cardItem: StatementItem = {
        id: crypto.randomUUID(),
        kind: "statement",
        filename: file.name,
        result,
      };
      setMessages((prev) =>
        prev.flatMap((m) =>
          m.id === progressId ? [summaryMsg, cardItem] : [m],
        ),
      );
    } catch (err) {
      window.clearInterval(tickHandle);
      const errMsg = (err as Error).message || "upload failed";
      // Leave the progress card visible with its error state so the
      // user can see WHICH step failed.
      setMessages((prev) =>
        prev.map((m) =>
          m.id === progressId && "kind" in m && m.kind === "import-progress"
            ? { ...m, errorMessage: errMsg, elapsedMs: Date.now() - startedAt }
            : m,
        ),
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <AppShell activeHref="/chat" glow={false}>
      <div className="mx-auto flex h-[calc(100svh-4rem)] w-full max-w-3xl flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
          <div className="flex flex-col gap-4">
            {messages.map((m) => {
              if ("kind" in m && m.kind === "intervention") {
                return (
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
                );
              }
              if ("kind" in m && m.kind === "statement") {
                return (
                  <div key={m.id} className="flex justify-start">
                    <StatementCard result={m.result} filename={m.filename} />
                  </div>
                );
              }
              if ("kind" in m && m.kind === "import-progress") {
                return (
                  <div key={m.id} className="flex justify-start">
                    <ImportProgress
                      filename={m.filename}
                      events={m.events}
                      errorMessage={m.errorMessage}
                      elapsedMs={m.elapsedMs}
                    />
                  </div>
                );
              }
              return <Bubble key={m.id} message={m as ContentMessage} />;
            })}
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
            {/* V4 — bank-statement upload. Hidden input, paperclip
                button triggers file picker, sanity-checks .pdf, posts
                to /api/ingest/statement, and the StatementCard render
                happens via the message thread. */}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || streaming}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-white/[0.08] bg-[color:var(--color-surface)]/60 text-[color:var(--color-fg-muted)] backdrop-blur-xl transition-colors hover:border-[color:var(--color-accent)]/40 hover:bg-[color:var(--color-surface-hi)]/60 hover:text-[color:var(--color-fg)] disabled:cursor-not-allowed disabled:opacity-50"
              aria-label={uploading ? "Reading statement" : "Upload a bank statement PDF"}
              title="Upload a bank statement PDF"
            >
              {uploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder={uploading ? "Reading your statement…" : "Tell MoneyMind what's going on…"}
              rows={1}
              disabled={streaming || uploading}
              className="max-h-40 min-h-[44px] flex-1 resize-none rounded-2xl border border-white/[0.08] bg-[color:var(--color-surface)]/60 px-4 py-2.5 text-sm leading-6 outline-none backdrop-blur-xl transition-colors placeholder:text-zinc-500 focus:border-[color:var(--color-accent)] focus:ring-2 focus:ring-[color:var(--color-accent)]/20 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!input.trim() || streaming || uploading}
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

// Short currency formatter for chat-thread summary lines (so we don't
// pull the whole Intl machinery into the upload handler).
function formatTotal(n: number): string {
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
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
