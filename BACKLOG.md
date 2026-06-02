# MoneyMind — Product Backlog

**Code freeze:** 2026-06-04 (Thursday) · **Submission:** 2026-06-11

## Legend

- **Status:** `⬜ todo` · `🟡 wip` · `✅ done (YYYY-MM-DD)` · `🚧 blocked` · `🧊 post-freeze` (deferred to after Jun 4)
- **Size:** `S` = ½ day · `M` = 1 day · `L` = 2 days · `XL` = 3+ days
- **Owner:** `@mahyar` (agent) · `@kasra` (backend) · `@aidin` (frontend)
- **Demo proof:** if this lands, this is what shows up in the demo video. If you can't name a demo proof, the item is busywork — cut it.

## Rules

1. **Nothing leaves the backlog without a demo proof.** If it won't appear in the 90-second video or the live walkthrough, it doesn't ship.
2. **Keep status current.** `todo → wip → done → blocked`. Update the row when state changes.
3. **Owners are locks, not suggestions.** If you're stuck, escalate before the end of the day — don't silently fall behind.
4. **Out-of-scope items stay out.** New ideas after Sprint 1 go to `## Won't ship`, not to the top of the list.

---

## Sprint 1 — Foundations (May 21 → May 26)

> **Goal:** end-to-end walking skeleton. Push a CSV in, get an agent paragraph out. Schemas locked, contracts agreed.

| #   | Status | Item                                                                                                       | Owner    | Size | Demo proof                              |
| --- | ------ | ---------------------------------------------------------------------------------------------------------- | -------- | ---- | --------------------------------------- |
| 1   | ✅ done (2026-05-21) | Atlas cluster + IAM + connection string in `.env.example`                                | @mahyar  | S    | M0 cluster `moneymind` live in us-east-1, user `moneymind-app` created, network `0.0.0.0/0`, connection string in shared Doc |
| 2   | ✅ done (2026-05-21) | Collections: `transactions`, `goals`, `memories`, `interventions`, `outcomes`, `user_context`             | @mahyar  | M    | Schemas in `docs/data-model.md`. `memories` materialized for vector index. Other collections auto-create on first write (verified by PR #2 ingest). |
| 3   | ✅ done (2026-05-21) | Vector index on `memories.embedding`                                                     | @mahyar  | M    | `memories_vector_idx` READY, 1024 dim cosine, filters on `user_id` + `type` |
| 4   | ✅ done (2026-05-21) | CSV ingest endpoint `POST /ingest/csv` → `transactions` collection                          | @kasra   | M    | PR #2 merged. All 3 blocking issues fixed across commits 7b68c20, 0e3cc7d, 5081cad. Awaits synthetic data (#6) to verify "6mo loads cleanly." |
| 5   | ✅ done (2026-05-26) | Aggregation: weekly spend by category                                                       | @kasra   | S    | PR #3 merged. Both blocking issues fixed: required `user_id`, end-of-day upper bound (param renamed `date_to_exclusive`). 3 new tests cover naive/aware/upper-bound cases. |
| 6   | ✅ done (2026-05-26) | Synthetic dataset generator (1 user, 6 months, realistic patterns)                          | @kasra   | L    | PR #4 merged. 331 rows, seeded RNG, both stress events present (Feb exam week + May work week). |
| 7+8 | ✅ done (2026-05-27) | Next.js scaffold + Clerk + dark theme + streaming chat shell (bundled in PR #7)                           | @aidin   | M+M  | PR #7 reviewed MERGE 2026-05-27. `Show` import bug fixed. Sign in → /dashboard, type → tokens stream from echo handler. Two follow-ups spun out: #7a (Clerk keys → `.env.example`), #8b (lock SSE wire format). |
| 9   | ✅ done (2026-05-21) | LangGraph minimum: 1 node, Gemini call, returns a paragraph                                  | @mahyar  | M    | Hello-world loop runs locally. PR open as `agent/9-langgraph-min`. 4/4 tests pass, real Gemini reply on curl. Boots via `PYTHONPATH=.. uv run uvicorn agent.serve:app --port 8001`. |
| 10  | ✅ done (2026-05-27) | Glue: frontend → `/chat` → agent → MongoDB read → response                                  | all      | M    | **Walking skeleton LIVE** against real Atlas + Gemini. Full chain: 330 rows seeded → POST /chat (frontend→backend→agent→/agg/weekly→Gemini) → streamed reply citing 3 real figures (food.delivery $211.21, total $436.33, Amazon $73.13), all matching the aggregation. Agent tests 3✓, backend 8✓, ruff clean. Closes #8a. |

**Bonus done today (2026-05-21):** Gemini, Voyage, and Clerk API keys provisioned + saved to shared Google Doc. Both teammates can run `cp .env.example .env`, paste values, and connect.

**Sprint 1 demo (May 26):** Walking skeleton. "Here's a CSV, here's an agent reply that references real numbers from it."

**Hard stop if not done:** if items 1–10 aren't all green by EOD May 26, replan before starting Sprint 2. Do not grind into Sprint 2 on a broken foundation.

---

## Sprint 2 — The Agent (May 27 → Jun 2)

> **Goal:** all 10 agent tools live, weekly cron loop, intervention approval flow. The slide-8 scenario works live.

| #   | Item                                                          | Owner    | Size | Demo proof                              |
| --- | ------------------------------------------------------------- | -------- | ---- | --------------------------------------- |
| 11  | ✅ done (2026-05-27) Tool: `query_transactions(filters)`        | @mahyar  | S    | LANDED. `agent/tools/query_transactions.py` + `agent/db/client.py` + 12 tests. Verified on real Atlas: filter category=food.delivery, dates 2026-05-18→05-23 returns 8 DoorDash rows, boundary inclusivity proven. Ruff clean. LangGraph wiring deferred to batched migration ticket (see #11a). |
| 12  | ✅ done (2026-05-31) Tool: `get_spend_anomaly(category, window)` | @mahyar  | M    | LANDED. `agent/tools/get_spend_anomaly.py` + `agent/aggregations/weekly.py` (mirror, for #20) + 10 tests. Both demo windows fire correctly on live Atlas: May stress z=63.68, Feb stress z=124.66; quiet transit returns std=0 / z=0. 25 tests green, ruff clean. Wired via #11a. |
| 13  | ✅ done (2026-05-31) Tool: `recall_memory(query, k=5)` via vector search | @mahyar | M | LANDED. `agent/tools/recall_memory.py` + `agent/embeddings/voyage.py` (embed_query + embed_document) + 27 new tests + live demo script. Verified on real Atlas + real Voyage: 3 seeded memories, 3 queries each surface the right top hit (food_spike→no_prep 0.700, morning_coffee 0.748, monthly_rent 0.722). 54 total agent tests green, ruff clean. Wired via #11a. **Surfaced #3a** (auto-embed not actually configured) and **#13a** (use_count bump). |
| 14  | ✅ done (2026-06-01) Tool: `write_memory(type, evidence, confidence)` | @mahyar | S | LANDED. `agent/tools/write_memory.py` + 19 hermetic tests + live demo. Path A (writer embeds inline) per the standing decision. Persisted shape matches docs/data-model.md § memories exactly. **R+W loop now works end-to-end on real Atlas** — wrote a pattern, recalled via #13 with semantic query, score=0.766. 73 total agent tests green, ruff clean. Wired via #11a. |
| 15  | ✅ done (2026-06-01) Tool: `update_user_context(text)` ("I'm bulking") | @mahyar | S | LANDED. `agent/tools/update_user_context.py` (94 lines) + 16 hermetic tests via `_fakes` (#14a) + live demo. Insert-only — never supersedes. Demo verified the **active-on-date predicate** against real Atlas: today (2026-06-01) finds the ongoing "bulking" context, Feb 15 finds the exam-week context. 88 total agent tests green, ruff clean. Predicate now formalized in data-model.md so #11a's graph node has one canonical reader. Wired via #11a. |
| 16  | ✅ done (2026-06-01) Tool: `check_goal_pace(goal_id)`           | @mahyar  | S    | LANDED. `agent/tools/check_goal_pace.py` + 16 hermetic tests + live demo. Single read via find_one; 8-verdict ladder (active goals: ahead / on_track / behind / past_due / not_started / complete; status-driven: paused / abandoned). ±5% tolerance band. ObjectId validated BEFORE the DB hit (tripwire test proves find_one was never called on invalid input). Demo walked all 4 active verdicts on the same goal: not_started → behind (-27.7%) → past_due → complete. 104 tests green, ruff clean. |
| 17  | ✅ done (2026-06-01) Tool: `propose_intervention(type, params)` | @mahyar  | M    | LANDED. `agent/tools/propose_intervention.py` (106 lines) + 17 hermetic tests via `_fakes` (#14a) + live demo. Write-only: single `insert_one` of a PENDING doc. Persisted shape matches docs/data-model.md § interventions + two additions: `user_response`/`responded_at` explicitly null, NEW `status: "pending"` field for cheap reader filtering. `triggered_by` REQUIRED. `related_memory_id` validated as ObjectId BEFORE the DB hit (tripwire pattern from #16). Live demo verified the entire pending-shape contract via find_one round-trip. 140 tests green, ruff clean. **Surfaced #17a** (respond_to_intervention contract), **#17b** (intervention index), and the **#17-wire** follow-up to batch #16 + #17 into the graph. |
| 18  | ✅ done (2026-06-01) Tool: `log_outcome(intervention_id, result)` | @mahyar  | S    | LANDED. `agent/tools/log_outcome.py` (112 lines) + 20 hermetic tests via `_fakes` (#14a) + live demo. Write-only single `insert_one`. **`delta_pct` is server-computed** from `before/after` (input model does NOT have a delta_pct field) using `abs(before)` so sign reflects direction-of-change for negative baselines. `before=0` → `0.0` deterministic (no division error). `intervention_id` validated as ObjectId BEFORE the DB hit (tripwire pattern, third tool to use it). Live demo verified server-computed `-34.17%` matches the worked example exactly. 160 tests green, ruff clean. |
| 19  | ✅ done (2026-06-01) Tool: `schedule_reminder(when, what)`     | @mahyar  | S    | LANDED. `agent/tools/schedule_reminder.py` (121 lines) + 16 hermetic tests + live demo. Write-only single `insert_one` to NEW `atlas.reminders` collection (first writer; data-model amended). Distinct from #17 interventions: no approval flow, no outcome, one-off fire. `source: user \| agent` discriminator, `status: pending` on write, `fires_at` is **UTC-aware** (deliberate exception to convention 5; documented). Naive coercion + past-rejection at validator. ObjectId tripwire on `related_intervention_id`. Demo verified the canonical "pending due by T" predicate the #21 cron will use: both reminders found, ordered by fires_at asc, T=now+5d returns only the 3-day. 176 tests green, ruff clean. |
| 20  | ✅ done (2026-06-01) Tool: `summarize_week()`                  | @mahyar  | M    | LANDED. `agent/tools/summarize_week.py` (283 lines) + 20 hermetic tests + live demo. Read-only, no tool nesting (composition lives in the agent layer). Reads from TWO collections (transactions, goals) via two kwargs + an `aggregator` kwarg (first tool with three injectables — pattern lets prod use real `$dateTrunc` while tests skip it). Returns BOTH structured fields (LLM reasoning) AND a ready-to-post paragraph (cron inbox). ISO Monday-Sunday weeks. Demo verified live: $340 / 8 txn / 4 categories / 1 goal "Behind by 9pp" → paragraph reads "Week of Mon, May 18: you spent $340 across 8 transactions. Biggest categories: Food Delivery $211, Shopping Amazon $73, Food Coffee $32. You're 30% to Emergency Fund — behind by 9pp." 196 tests green, ruff clean. **`_DESCRIPTIONS`' forward reference to `summarize_week` is now truthful pending #17-wire.** |
| 21  | ✅ done (2026-06-02) Weekly inbox + reminder runner            | @kasra   | M    | LANDED (PR #39 merged, R3). User-triggered POST `/agent/run-weekly-summary` + POST `/agent/run-reminders` + GET `/inbox` — all Clerk-authenticated. New `inbox_messages` collection (smaller shape than draft: no `status`, no `read_at` — tests pin absent fields). Backend `fetch_agent_weekly_summary` sends `X-MoneyMind-User-Id` to agent's loopback `/chat` (#4a contract). Reminders runner dedups `fired` + `skipped`. **Closes #17b** (compound index on interventions). 2 new indexes on inbox_messages + 1 on reminders. Scheduled-by-cron deferred to post-freeze; for demo it's button-triggered. |
| 22  | Intervention approval flow UI (accept / decline / modify)     | @aidin   | M    | Buttons work + state persists           |
| 23  | Dashboard page: spend chart, goals, recent memories           | @aidin   | L    | Looks like a real product               |
| 24  | Wire MongoDB MCP server into agent                            | @mahyar  | M    | Agent self-tunes one query in demo      |

**Sprint 2 demo (Jun 2):** The slide-8 scenario, working live. Agent notices food spike → asks → user replies → memory writes → confirmation.

---

## Sprint 3 — Polish (Jun 3 → Jun 4) · CODE FREEZE Jun 4 EOD

> **Goal:** two days. No new features. Voice, motion, demo video, Devpost. If item #27 (the video) is at risk, kill anything else.

| #   | Item                                                                  | Owner            | Size | Demo proof                       |
| --- | --------------------------------------------------------------------- | ---------------- | ---- | -------------------------------- |
| 25  | Agent voice tuning (prompt iteration on 10 scenarios)                 | @mahyar          | M    | Reads warm + concrete, not robotic |
| 26  | Frontend animations + visual polish (pitch-deck quality)              | @aidin           | M    | Feels premium on first 5 sec     |
| 27  | **Demo video — script, record, edit (90s max)**                       | @aidin + all     | L    | `demo.mp4` in repo               |
| 28  | Devpost writeup (cribbed from pitch deck + README)                    | @mahyar          | M    | Draft submitted, link in repo    |
| 29  | Smoke test full flow on prod with fresh user                          | all              | S    | No errors, no console warnings   |
| 30  | Tag `v1.0` and freeze main branch                                     | @mahyar          | S    | Tag pushed, branch protected     |

---

## Open follow-ups

> Done items have been pruned. If it's not here, it's either complete or out of scope.

| #   | Status | Item                                                                | Owner    | Size | Why                                                  |
| --- | ------ | ------------------------------------------------------------------- | -------- | ---- | ---------------------------------------------------- |
| 11b | 🚨 **DEMO BLOCKER** | **Atlas dedup + source-key fix.** `u_482` rows are doubled on the demo cluster (`#12` reported `$422.42` vs. the auditable `$211.21`; `#11a` live demo confirmed 670 rows for u_demo_graph_11a instead of ~330). Verdicts survive scaling but absolute dollars in the demo paragraph won't match the CSV. Investigate the duplicate `source` collision, dedupe, tighten the source key. | @kasra | S | CANNOT record demo video until fixed. |
| 12a | 🟡 partial (2026-06-01) | **Add `* 2.*` patterns to `.gitignore`** so Finder/iCloud can't silently recreate duplicates. The byte-identical `chat 2.py` was deleted from the working tree 2026-06-01 after 11 consecutive dev reports flagged it. Patterns to add: `* 2.py`, `* 2.ts`, `* 2.tsx`, `* 2.json`, `* 2.md`. | @kasra | S | Half done — the file is gone. Bundle the gitignore addition into the next backend PR. |
| 7a  | ⬜ todo | **Add the two FRONTEND Clerk keys to `.env.example`** (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY`). Kasra already landed `CLERK_JWT_ISSUER` + `CLERK_JWT` via #4a; this is the half Aidin owns. Without it, next dev to pull can't run the frontend. | @aidin | XS | Onboarding blocker; smaller now that Kasra got the JWT side. |
| 6a  | ⬜ todo | **One-shot seed script** — `make seed` pipes `data/synthetic.csv` → `POST /ingest/csv`. Removes manual onboarding step. | @kasra | S | Quality-of-life, not blocking. |
| 13a | ⬜ todo | **Tool: `mark_memory_used(memory_id)`** — bumps `last_used` + `use_count` when the agent actually CONSUMES a recalled memory (not just retrieves). Deliberately split from #13 so read and consume can diverge. | @mahyar | S | Data-model implies the bump; this is who does it. |
| 21a | ⬜ todo | **Week-definition drift — pin ONE canonical "week".** Four different week implementations now coexist: backend cron uses Python `weekday()`, agent `#20 summarize_week` uses the same, backend `/agg/weekly` uses Mongo `$dateTrunc startOfWeek: monday`, agent `#12 get_spend_anomaly` uses anchored 7-day buckets. All happen to agree for ISO Monday weeks today, but the divergence is fragile. Pin ONE definition in `docs/architecture.md` (likely "ISO week, Monday start, inclusive both ends") and require all new aggregations to call into a shared helper. | @mahyar | S | Surfaced by #21 review. Risk: a fifth definition slips in via #23 or #25 work, and the dashboard reads a different week than the cron wrote. |
| 23a | ⬜ todo | **Dashboard must render `/inbox`** — Kasra's #21 ships JSON at GET `/inbox` with weekly-summary + reminder messages. There's no UI consumer yet. The demo video's "agent posts to inbox" beat depends on Aidin surfacing it visibly somewhere in `#23`. | @aidin | S | Surfaced by #21 review. Without this, `/inbox` is invisible product — Kasra shipped a backend the user can't see. |
| 13b | ⬜ todo | **External-service rate-limit hardening (Voyage + Gemini).** Voyage free tier ~3 RPM (#13 hit a 5-min wait; #14 needed 20s gap on a single round-trip). **Gemini free tier 20 generate_content requests/day** (surfaced by #17a-wire's live demo — 2-turn demo hit it). Voyage options: upgrade, batch (128/call), jittered backoff. Gemini options: upgrade, quota-aware retry queue. Both block on cost calls. | @mahyar | S | Voyage cascade could brick #21 cron; Gemini quota burns through #25p iteration in an hour. |
| 25p | ⬜ todo | **Prompt + template tuning targets** (folds into Sprint 3 #25). (a) When "this week" has no data, fall back to the most recent populated week — same semantics as #12, surfaced in #11a's live demo. (b) When `active_context_block` is injected, reference it explicitly in the reply — wiring provably correct but Gemini ignored it on #11a's Turn 3. (c) `summarize_week`'s paragraph template is rigid v1 — once we have 10 real weekly digests on real data, soften the deterministic phrasing without losing the whole-dollar / no-markdown contract. (d) **Reinforced by #17-wire's live demo**: when `summarize_week` returns `total_spend=0` AND recent goal data exists, the prompt should nudge Gemini to either retry with `week_offset=-1` OR explicitly say "no data this calendar week, here's last week." Today Gemini's reply says "you haven't recorded any spending this week" — technically true but unhelpful when the auditable CSV ends a week ago. **Primitive to use:** `agent/scripts/demo_graph_full.py` instruments which tools Gemini actually picks in a real turn — that's the feedback loop voice-tuning needs. | @mahyar | — | Not a separate Sprint 2 ticket; pre-loads #25's iteration list. |
| 11a-1 | 🧊 post-freeze | **Migrate `langgraph.prebuilt.create_react_agent` → `langchain.agents.create_agent`.** Pytest emits `LangGraphDeprecatedSinceV10` warning. Working as of langgraph 1.x; will need to move before LangGraph 2.0. | @mahyar | S | Surfaced by #11a. Pure rename + import swap. |
| 9b  | 🧊 post-freeze | **Agent boot ergonomics** — drop the `PYTHONPATH=..` requirement. Editable install via hatchling caused pytest to hang in #9; the current `PYTHONPATH=..` workaround is documented in `agent/README.md`. | @mahyar | S | Cosmetic; not on the critical path. |
| 3a  | 🧊 post-freeze | **Optionally configure Atlas auto-embed on `memories.summary`.** The current working pattern (writers call `voyage.embed_document()` before insert) is decided + logged. If we ever flip auto-embed, drop the explicit embed call from #14 + #21. | @mahyar | S | Reversible later; no demo impact. |

---

## Post-freeze (Jun 5 → Jun 10) — submission buffer

- **Bug fixes only.** No new features. Treat code as locked.
- Re-record video if needed.
- Finalize Devpost copy. Have all three teammates review.
- Practice the live demo walkthrough at least 3x.

---

## Won't ship (out of scope)

- Real bank connections (Plaid). **Use CSV.**
- Mobile app. Web only.
- Multi-user accounts beyond a demo seed user.
- Email/SMS delivery for nudges. In-app inbox only.
- Anything not on the critical path to slide 8 working live.

---

## Risks + mitigations

| Risk                                          | Likelihood | Mitigation                                             |
| --------------------------------------------- | ---------- | ------------------------------------------------------ |
| Vector search latency too high                | Low        | Cache top-k recalls per user · pre-embed on write      |
| Gemini rate limits during demo                | Medium     | Pre-record fallback video · stub responses ready       |
| Synthetic dataset feels fake on camera        | High       | @kasra spends extra time on realistic patterns wk 1    |
| Demo video runs over 90s                      | High       | Storyboard before recording · cut one beat if needed   |
| One teammate gets sick / disappears 48h       | Low        | Each swim lane shippable independently (see slide 14)  |
