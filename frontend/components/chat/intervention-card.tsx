"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeftRight,
  Bell,
  CheckCircle2,
  Gauge,
  MessageCircle,
  Sparkles,
  X,
  type LucideIcon,
} from "lucide-react";
import type {
  Intervention,
  InterventionResponse,
  InterventionType,
} from "@/lib/interventions";
import { interventionCopy } from "@/lib/interventions";

const ICON: Record<InterventionType, LucideIcon> = {
  reminder: Bell,
  cap: Gauge,
  swap_suggestion: ArrowLeftRight,
  reflection: MessageCircle,
};

const RESOLVED: Record<InterventionResponse, { label: string; good: boolean }> = {
  accepted: { label: "Accepted", good: true },
  modified: { label: "Updated", good: true },
  declined: { label: "Declined", good: false },
  ignored: { label: "Dismissed", good: false },
};

const DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

const PRIMARY_BTN =
  "rounded-xl bg-[color:var(--color-accent)] px-4 py-2 text-sm font-semibold text-zinc-950 shadow-[0_1px_0_0_rgba(255,255,255,0.25)_inset] transition-colors hover:bg-[color:var(--color-accent-hi)] disabled:opacity-50";
const GHOST_BTN =
  "rounded-xl border border-white/10 bg-white/[0.02] px-4 py-2 text-sm text-[color:var(--color-fg-muted)] transition-colors hover:bg-white/[0.06] hover:text-[color:var(--color-fg)] disabled:opacity-50";

export function InterventionCard({
  intervention,
  onRespond,
}: {
  intervention: Intervention;
  onRespond: (
    response: InterventionResponse,
    modifiedParams?: Record<string, string>,
  ) => void | Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(intervention.params).map(([k, v]) => [k, String(v)]),
    ),
  );

  const Icon = ICON[intervention.type];
  const { title, body, cta } = interventionCopy(intervention);
  const resolved =
    intervention.status !== "pending" && intervention.user_response
      ? RESOLVED[intervention.user_response]
      : null;

  async function respond(
    response: InterventionResponse,
    modifiedParams?: Record<string, string>,
  ) {
    if (busy) return;
    setBusy(true);
    await onRespond(response, modifiedParams);
    setBusy(false);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="relative max-w-[85%] overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-[color:var(--color-surface-hi)] to-[color:var(--color-surface)] p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.05)_inset,0_16px_50px_-20px_rgba(0,0,0,0.85)]"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--color-accent)]/50 to-transparent" />

      <div className="mb-3 inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
        <Sparkles className="h-3 w-3" />
        Suggested
      </div>

      <div className="flex items-start gap-3.5">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)] ring-1 ring-inset ring-[color:var(--color-accent)]/20">
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold tracking-tight text-[color:var(--color-fg)]">
            {title}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-[color:var(--color-fg-muted)]">
            {body}
          </p>

          {resolved ? (
            <div
              className={
                resolved.good
                  ? "mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--color-accent)]/10 px-3 py-1.5 text-sm font-medium text-[color:var(--color-accent)] ring-1 ring-inset ring-[color:var(--color-accent)]/20"
                  : "mt-4 inline-flex items-center gap-1.5 rounded-lg bg-white/[0.03] px-3 py-1.5 text-sm text-[color:var(--color-fg-muted)] ring-1 ring-inset ring-white/10"
              }
            >
              {resolved.good ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <X className="h-4 w-4" />
              )}
              {resolved.label}
            </div>
          ) : editing ? (
            <div className="mt-4 flex flex-col gap-3">
              {Object.keys(draft).map((key) => (
                <div key={key} className="flex flex-col gap-1.5">
                  <span className="text-xs capitalize text-[color:var(--color-fg-muted)]">
                    {key.replace(/_/g, " ")}
                  </span>
                  {key === "day" ? (
                    <div className="flex flex-wrap gap-1.5">
                      {DAYS.map((d) => {
                        const active = draft.day === d;
                        return (
                          <button
                            key={d}
                            type="button"
                            onClick={() => setDraft((s) => ({ ...s, day: d }))}
                            className={
                              active
                                ? "rounded-lg bg-[color:var(--color-accent)] px-2.5 py-1.5 text-xs font-semibold text-zinc-950"
                                : "rounded-lg border border-white/10 bg-white/[0.02] px-2.5 py-1.5 text-xs text-[color:var(--color-fg-muted)] transition-colors hover:bg-white/[0.06] hover:text-[color:var(--color-fg)]"
                            }
                          >
                            {d.slice(0, 3)}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <input
                      value={draft[key]}
                      onChange={(e) =>
                        setDraft((s) => ({ ...s, [key]: e.target.value }))
                      }
                      className="rounded-lg border border-white/10 bg-[color:var(--color-bg)] px-3 py-2 text-sm text-[color:var(--color-fg)] outline-none transition-colors focus:border-[color:var(--color-accent)]/60"
                    />
                  )}
                </div>
              ))}
              <div className="mt-1 flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => respond("modified", draft)}
                  className={PRIMARY_BTN}
                >
                  Save
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setEditing(false)}
                  className={GHOST_BTN}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => respond("accepted")}
                className={PRIMARY_BTN}
              >
                {cta}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => respond("declined")}
                className={GHOST_BTN}
              >
                Decline
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(true)}
                className={GHOST_BTN}
              >
                Modify
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
