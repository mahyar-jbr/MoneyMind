# MoneyMind — Product Backlog

**Code freeze:** 2026-06-04 (Thursday) · **Submission:** 2026-06-11 @ 2:00 PM PT

---

## 🚨 RULES-COMPLIANCE — all infra closed

> All R-items shipped. **End-to-end live verified** 2026-06-06 17:02 EDT: 3-turn conversation with active-context recall, real Atlas data, intervention card render, all responses under 5s after warmup. Only R8 (Devpost) + R9 (video) remain — both independent of code.

| # | Item | Owner | Size |
| --- | ---- | ----- | ---- |
| R2 | ✅ **done 2026-06-05** — Vertex AI migration verified live in PROD. `moneymind-agent@moneymind-hack.iam` SA, `roles/aiplatform.user`, key as `GOOGLE_APPLICATION_CREDENTIALS_JSON_B64` (base64 — raw JSON corrupted PEM newlines). Import fix: `langchain_google_vertexai.chat_models` submodule (cold-import 236s → 2.1s). 222 tests, ruff clean. | @mahyar | — |
| R4 | ✅ **done 2026-06-05** — Live URLs: frontend https://money-mind-seven.vercel.app (Vercel, Next 15) + backend+agent https://moneymind-production-2a7e.up.railway.app (Railway, single Docker container). End-to-end verified: Clerk sign-in → dashboard renders $17,380/26-weeks → chat returns live Vertex Gemini reply. | @mahyar | — |
| R-budget | ✅ **done 2026-06-06** — GCP budget alert set on `moneymind-hack` at $300 with 50/90/100% triggers. | @mahyar | — |
| R1 | ✅ **done 2026-06-06** — MongoDB MCP server wired as first-class tool source. `agent/mcp_integration/client.py` lazy-spawns `npx mongodb-mcp-server@latest --readOnly` on first `get_mcp_tools()`; MCP tools get `mongo_` prefix and join the 11 native tools in `create_react_agent(tools=)`. `_build_tools` + `build_graph` are async; cascaded through `arun_chat`, `stream_chat`, 14 test_graph callsites. `--readOnly` (camelCase) hardcoded + enforced by `test_server_config_includes_read_only_flag` — kebab-case form was caught failing in Railway logs and fixed in `48f23e6`. Graceful fallback: spawn failure returns `[]`, agent still boots with 11 native tools. `MONGODB_MCP_DISABLE=1` env-var kill switch wired in `e62fe51` in case the upstream `mongodb-mcp-server` package regresses (it currently ships with a `Cannot find module 'vary'` transitive bug; native tools cover everything end-to-end). 232 → 242 tests; conftest.py autouse stubs `get_mcp_tools` to `[]` in graph tests. README + system prompt updated. | @mahyar | — |
| R-infra | ✅ **done 2026-06-06 EOD** — Production-correctness fixes caught during live end-to-end testing: (1) **lifespan warmup** in `agent/serve.py` so the heavy graph import (langchain_google_vertexai + langgraph + 11 tools, 30–240s cold) runs on a background thread during FastAPI's lifespan startup; uvicorn announces 'ready' in <1s and Railway healthcheck no longer risks restart-loop. (2) **`astream_chat`** added in `agent/graphs/main.py`; serve.py's async `/chat` handler awaits it via `async for` — every request stays on a single event loop, motor cursors no longer cross loops (`RuntimeError: Event loop is closed` on second-message-onwards reproduced + fixed). (3) Vercel `/api/chat` route now pipes upstream through an explicit `ReadableStream` so chunks flush instead of buffering; `X-Accel-Buffering: no` + `dynamic=force-dynamic` + `maxDuration=300` set. (4) Frontend `useEffect` unmount cleanup that called `abortRef.current?.abort()` removed — it was canceling in-flight chat requests at ~1.85s in prod. | @mahyar | — |
| R8 | **Devpost draft** — walk form, save draft, send team invites. Independent of R1/R2/R4. | @mahyar | XS |
| R9 | **Demo video: target 2:00-2:30**, not 90s. Cap is 3 min. Extra time = MCP-firing-on-camera + vector recall + intervention loop + memory beat. Independent. | @kasra | XS |

**Today's chain** (2026-06-06): closed R1 + R-budget + #25 + R-infra in one day. End-to-end conversation against the live URL is recorded in `README.md` (birthday-party demo). The only blockers remaining are non-code: Devpost prose, video, smoke pass on a fresh user.

---

**Sizes:** S = ½ day · M = 1 day · L = 2 days · XL = 3+ days
**Owners:** @mahyar agent · @kasra backend · @aidin frontend

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
| 22  | ✅ done (2026-06-02) Intervention approval card                  | @aidin   | M    | LANDED (PR #45 merged, R3). Three-state card (pending / modify / resolved) drops into chat thread after each turn. Day-of-week picker for reminders, Framer Motion entrance, premium accent styling. Types match #17 `propose_intervention` shape. **Mock-only**: `fetchPending` + `respondTo` are stubs returning one hardcoded reminder after the first message — agent's actual #17/#17a Atlas writes are invisible to the UI. Real backend tracked as **#22a** (demo-decision needed). |
| 23  | ✅ done (2026-06-02) Dashboard page                              | @aidin   | L    | LANDED (PR #43 merged, R3). `/dashboard` reads live data via two new Clerk-gated proxy routes (`/api/agg/weekly`, `/api/transactions`). StatCards (total / this week / top category / txn count) + hand-rolled SVG SpendChart + CategoryBreakdown + TransactionsList. Loading skeleton, error state, empty state. 9 new lib files isolate formatters + aggregations for testability. New env var precedence `BACKEND_URL > NEXT_PUBLIC_BACKEND_URL > default`. **Strongest visual beat for the demo video.** Goals + memories widgets deferred to follow-up (blocked on backend endpoints); `/inbox` rendering tracked as #23a. |

---

## Sprint 3 — Polish + Submission (Jun 3 → Jun 11)

| #   | Item                                                                  | Owner            | Size |
| --- | --------------------------------------------------------------------- | ---------------- | ---- |
| 25  | ✅ **done 2026-06-06** — Agent voice tuning (7d5efad + bdbeb15). Live-judged on prod; birthday-party + DoorDash co-recall verified. | @mahyar          | —    |
| 26  | ➡️ **superseded by V2** in the vision backlog (month selector + top-merchants + goal widget). Track there. | @aidin           | —    |
| 27  | **Demo video — script, record, edit (2:00-2:30, max 3min)**           | @kasra           | L    |
| 28  | Devpost writeup (full prose, replaces the placeholder draft). Must explicitly cite the SDK path + LangGraph + Vertex AI Gemini per the eligibility framing. | @mahyar          | M    |
| 29  | Smoke test full flow on live deployed URL with fresh user             | all              | S    |
| 30  | Tag `v1.0` and freeze main                                            | @mahyar          | S    |

---

## Open follow-ups

> Done items have been pruned. If it's not here, it's either complete or out of scope.

| #   | Status | Item                                                                | Owner    | Size | Why                                                  |
| --- | ------ | ------------------------------------------------------------------- | -------- | ---- | ---------------------------------------------------- |
| 22a-swap | ✅ **done 2026-06-06** | Real intervention wiring shipped (ad94ab3). New proxy routes, fromBackend adapter remaps `id → intervention_id`, snake_case respond body, chat-page dedup against rendered intervention_ids. Live-verified: real Atlas ObjectId `6a24996b47fb51e75e8b7f29` written + pending→responded flip on prod. | @mahyar | — | — |
| 23a-seed | 🟡 **before recording** | **Trigger `/agent/run-weekly-summary` + `/agent/run-reminders` against the demo user** so the inbox has populated content on camera. POST both endpoints once before each take. | @mahyar | XS | 30 seconds of curl per take. |

---

## 🔭 Vision backlog — "real finance app" enhancements (post-MVP)

> Added 2026-06-06 EOD after walking through what the agent **can't** do today vs. the pitch's promise. The product already works end-to-end with memory + active context + interventions, but these four items are the gap between "demo of an idea" and "ship it tomorrow". Each entry below has been fact-checked against the shipped code; current_state cites what's actually there.

### V1 — Goals: create + read via chat or dashboard

**Current state (verified 2026-06-06):**
- ✅ `check_goal_pace` tool exists in [`agent/tools/check_goal_pace.py`](agent/tools/check_goal_pace.py) — reads a goal by `goal_id`, returns pace verdict (ahead/on_track/behind/past_due/...).
- ✅ Goals collection schema documented in [`docs/data-model.md`](docs/data-model.md).
- ❌ No `write_goal` / `list_goals` / `update_goal` agent tools exist.
- ❌ No `/goals` backend route exists (`backend/app/api/` has no goals file).
- ❌ No frontend goals UI (`grep -rln "goals" frontend/` returns only the home-page mention).
- ❌ User's Atlas `goals` collection is empty for the Clerk user (`count_documents({user_id: ...})` returned 0).
- 🔴 **`check_goal_pace` is unusable in practice** — the agent has no way to discover a `goal_id` to pass in. Today the goal beat is invisible.

**Scope (minimum for demo):**
- Add `write_goal(title, target_amount, target_date, current_amount=0)` agent tool — single insert into `goals`.
- Add `list_goals()` agent tool — returns user's goals so the LLM can decide which `goal_id` to feed `check_goal_pace`.
- Backend: optional — agent tools write directly to Atlas via motor, no backend route needed for the chat path. Add `GET /goals` only if dashboard needs it.
- Dashboard widget: read goals via new `GET /goals`, render alongside StatCards. Empty state with "ask MoneyMind to set a goal" copy.

**Files to touch:** `agent/tools/write_goal.py` (NEW), `agent/tools/list_goals.py` (NEW), `agent/graphs/main.py` (register 2 tools + descriptions), `agent/prompts/system.py` (1 paragraph on goal triggers — "user mentions saving for X, call write_goal"), `backend/app/api/goals.py` (NEW, GET only), `frontend/components/dashboard/goals-widget.tsx` (NEW), `frontend/app/dashboard/page.tsx` (mount it).

**Pattern reference:** mirror the write_memory + check_goal_pace pattern. tool → _wrap_tool registration → backend GET route → dashboard widget reads via Clerk proxy. Same flow as the intervention wiring shipped today.

**Effort:** 4-6h for @mahyar (agent tools + backend GET + dashboard widget all on the same head).
**Owner:** @mahyar (full stack)
**Demo value:** HIGH — closes the "agent learns about your goals" slide which is currently invisible.
**Risk:** LOW — additive only, no existing tool changes.
**AC:**
- [ ] User says "I want to save $5000 for a trip to Japan by December" → agent calls `write_goal` → returns `goal_id`.
- [ ] User says "how am I doing on my goals?" → agent calls `list_goals` then `check_goal_pace` for each → reply names actual progress.
- [ ] Dashboard renders goals widget with progress bars and pace status.
- [ ] Empty state shows on dashboard until first goal exists.

**Recommendation:** **ship-must** — without this, slide-7 (goal pace) is a dead demo beat.

---

### V2 — Dashboard polish: month selector + better charts

**✅ DONE 2026-06-07** — PR #52 merged (commit `d6730d5`, squash `f2c4146`). Aidin rebuilt the dashboard. Three demo-blockers caught in post-merge review + fixed inline; no separate follow-up PR needed.

**What shipped (PR #52):**
- NEW [`frontend/components/dashboard/widgets.tsx`](frontend/components/dashboard/widgets.tsx) (~550 lines) — 11 widgets: `KpiRow`, `InsightsPanel`, `TrendChart`, `BudgetProgress`, `CategoryBreakdown`, `IncomeExpenses`, `UpcomingBills`, `SavingsGoals`, `LargestPurchases`, `DashboardFilters`, plus `CARD` constant + `Panel`/`Kpi`/`Bar`/`DemoTag` primitives. Replaces the deleted [`spend-chart.tsx`](frontend/components/dashboard/spend-chart.tsx), [`category-breakdown.tsx`](frontend/components/dashboard/category-breakdown.tsx), [`stat-cards.tsx`](frontend/components/dashboard/stat-cards.tsx).
- NEW [`frontend/lib/analytics.ts`](frontend/lib/analytics.ts) (~222 lines) — client-side aggregation over raw transactions: `buildBuckets` (week/month + category filter), `rankCategories`, `pctChange`, `savingsRate`, `largestPurchases`, `deriveInsights`. Avoided the backend `?month=` route work entirely by aggregating in the frontend (single `getTransactions(500)` call feeds everything reactively). Trade-off documented in [`analytics.ts:1-3`](frontend/lib/analytics.ts#L1-L3).
- NEW [`frontend/lib/demo.ts`](frontend/lib/demo.ts) — placeholder net worth / cash / budgets / goals / bills for widgets that have no backend yet. Each tagged with a visible "SAMPLE" pill (amber, see DemoTag fix below).
- Rebuilt [`frontend/app/dashboard/page.tsx`](frontend/app/dashboard/page.tsx) with `DashboardFilters` (week/month granularity + period picker + category dropdown) wired reactively across every widget.
- Chat polish in same PR: redesigned suggestion cards with icons (Sparkles/TrendingUp/PieChart/PiggyBank), `AppShell glow={false}` for chat page, plain background. Multi-turn wire (V3) intact.

**Post-merge fixes (3 demo-blockers caught in review, all confirmed real against shipped code, fixed in same branch):**

1. **Projection insight on stale month** — [`frontend/lib/analytics.ts:198-213`](frontend/lib/analytics.ts#L198-L213). `deriveInsights` computed "At this pace you'll spend about $X this month" against `months[months.length-1]` (latest bucket WITH data = May for u_482, synthetic data ends 2026-05-24) using today's clock (Jun 7). Formula `(may_spend / 7 days) * 30 days` would have rendered "$~14k this month" on camera. **Fix:** gate the projection so it only fires when `curr.key === currentKey` (computed from `now.getUTCFullYear() / getUTCMonth()`). Folded in PM's off-by-one fix (`new Date(yr, mo, 0)` → `Date.UTC(yr, mo, 0)`) while in the function. 3-line gate, 2-line UTC fix.

2. **DemoTag invisibility** — [`frontend/components/dashboard/widgets.tsx:37-46`](frontend/components/dashboard/widgets.tsx#L37-L46). Pre-fix: `text-[9px]`, `border-white/10`, `bg-white/[0.04]`, `text-fg-muted` — invisible at 1080p video compression. Judge would see "$82,400 Net worth" headline next to real spend KPIs and conclude the app is Plaid-linked, contradicting the MongoDB-track pitch ("CSV ingest, no bank linking"). **Fix:** bump to `text-[11px]` + `border-amber-300/40` + `bg-amber-400/15` + `text-amber-300` (matches the warn tone already used in InsightsPanel). Renamed pill text "demo" → "SAMPLE" — reads as placeholder more clearly than "demo" on a finance app.

3. **Category filter zeros income** — [`frontend/lib/analytics.ts:54-83`](frontend/lib/analytics.ts#L54-L83). `buildBuckets` applied `categoryFilter` BEFORE the inflow/outflow split, so picking category=food (or any spend category) dropped the salary transaction → `bucket.income = 0` → IncomeExpenses chart loses green bars → savings-rate KPI shows "n/a". Live the moment you click a category filter on camera. **Fix:** apply categoryFilter only to outflows (`!isInflow`). Inflows always counted regardless of category filter. 4-line patch.

**Files touched in post-merge fix:** [`frontend/lib/analytics.ts`](frontend/lib/analytics.ts) (+24/-7), [`frontend/components/dashboard/widgets.tsx`](frontend/components/dashboard/widgets.tsx) (+8/-2).

**Test results:**
- `pnpm exec tsc --noEmit` — clean
- Visual smoke (eye-test on dev server): category=food no longer zeros IncomeExpenses; SAMPLE pill visible at video distance; InsightsPanel no longer renders the "$14k this month" projection against May data.

**Deferred to post-freeze (won't fire on the canonical demo script, not worth touching tonight):**
- selectedKey not reset on category change (page.tsx:78) — only bites if user filters into a category with zero spend in the selected period.
- `prev` is "previous bucket" not "previous calendar period" — mislabels deltas across data gaps. Synthetic data is continuous May→present so won't trigger.
- Several useMemo dep tightening + dead exports (`topLevelSpend`, `savingsRate`, etc.). Bench-warmers.
- Process violation: PR branch `dashboard-chat-polish` had no area prefix or ticket ref. Accepted under freeze pressure.

**Owner:** @aidin (PR #52) + @mahyar (post-merge fixes)
**Recommendation:** SHIPPED — closes V2. Dashboard now passes the "real finance app" bar for the demo video.

---

### V3 — Agent deletes a wrong memory ("forget what I said about X")

**✅ DONE 2026-06-06 EOD.** Implemented + locally verified end-to-end against live Atlas.

**What shipped:**
- NEW [`agent/tools/forget_memory.py`](agent/tools/forget_memory.py) — soft-delete + confidence-gated single-turn confirmation pattern. Score ≥ 0.75 → tool deletes immediately + returns summary so the agent names what was forgotten. Score < 0.75 → returns `needs_confirmation=True` for the agent to quote the candidate back and ask. No match → returns `deleted=False`, `memory_id=None`.
- [`agent/tools/recall_memory.py`](agent/tools/recall_memory.py) — post-search `$match { deleted_at: null }` so soft-deleted memories never surface. `{$eq: null}` matches both missing and explicitly-null, so memories written before V3 land are still recalled — no migration needed.
- [`agent/tools/write_memory.py`](agent/tools/write_memory.py) — sets `deleted_at: null` on insert so the field is present on every new memory.
- [`agent/graphs/main.py`](agent/graphs/main.py) — `forget_memory` registered as the 12th native tool with a tool description that makes the call REQUIRED on any "forget X" / "you were wrong" / "delete that" message.
- [`agent/prompts/system.py`](agent/prompts/system.py) — new FORGETTING section with three result-shape branches + example replies. Anti-pattern added: never invent your own query, pass the user's words verbatim.
- NEW [`agent/tests/test_forget_memory.py`](agent/tests/test_forget_memory.py) — 7 hermetic tests including a user_id isolation tripwire (must never delete another user's memory) and a second-call-after-delete idempotency check.
- [`agent/tests/_fakes.py`](agent/tests/_fakes.py) — new `VectorSearchWritableCollection` that allows `update_one` (other writes still trip). `FakeCollection.aggregate` updated to honor post-search `$match deleted_at` filter.

**Bug caught + fixed during V3 development (production-relevant):**
The Atlas vector index `memories_vector_idx` does NOT declare `deleted_at` as a filterable field. Initial implementation put it inside the `$vectorSearch` filter → silent zero results, agent thought nothing matched. Fixed by moving the filter to a post-search `$match` stage. Production-correct without needing Atlas console reindexing. Same fix applied to recall_memory's pipeline.

**Live trace verified against real Atlas:**
```
before: memories visible=1 (tag=user_is_doordashing), soft-deleted=0
user: "forget that I'm DoorDashing every night, that was just one bad week"
agent CALL: forget_memory(query="I've been DoorDashing every night...")
tool: {deleted=true, memory_id=6a24a0c97..., summary=...}
agent reply: "Got it — I've forgotten that you were DoorDashing every night."
after: memories visible=0, soft-deleted=1
```

**Tests:** 45/45 memory-triad pass (write + recall + forget). Ruff clean.

**AC results:**
- [x] User says "forget that I'm DoorDashing" → agent calls forget_memory + Atlas flips deleted_at + agent names what was forgotten.
- [x] On low confidence the tool returns needs_confirmation=True; agent quotes the candidate before re-calling.
- [x] On no match the tool returns memory_id=null; agent says nothing matched.
- [x] recall_memory no longer surfaces soft-deleted memories (test_pipeline_filters_deleted + live trace).
- [x] user_id isolation tripwire in tests — must NEVER delete another user's memory.

**Owner:** @mahyar
**Recommendation:** SHIPPED — closes the "what if the agent learned the wrong thing?" privacy beat for the demo.

---

### V4 — CSV / bank statement upload + per-month transaction edit

**Current state (verified 2026-06-06):**
- ✅ Backend `/ingest/csv` exists in [`backend/app/api/ingest.py`](backend/app/api/ingest.py), Clerk-authed via `current_user`.
- ❌ No frontend UI for CSV upload (users can't bring their own data through the product).
- ❌ No `PATCH /transactions/:id`, no `DELETE /transactions/:id`, no `POST /transactions` (manual add).
- ❌ No PDF / image / statement parser anywhere in the codebase.

**Part A — CSV upload from chat/dashboard (the cheap, high-value half):**
- Add `+ Upload statement` button in chat composer (or as a Dashboard card).
- Vercel proxy: `frontend/app/api/ingest/csv/route.ts` — forwards multipart upload to backend with Bearer token.
- After upload, post a system message in chat: "Ingested N transactions from your statement."
- Trigger dashboard refresh.

**Part B — Bank statement PDF → CSV via Gemini (the expensive half — research result):**
- Gemini 2.5 Flash on Vertex AI **does support PDF/image input natively** (multimodal input, up to 3000 pages per call).
- Realistic for a single one-page Chase / RBC / TD statement. Lossy on:
  - Multi-currency statements (FX line items)
  - Refunds / pending vs posted
  - Multi-page statements with category footers
  - Foreign banks with non-standard layouts
- Cost: ~$0.01-0.05 per statement processed (Flash pricing × typical statement size).
- **Demo-day risk: HIGH.** If a judge uploads their actual bank PDF and the parse hallucinates an amount, the agent's analysis is now based on fake data. The memory loop poisons.
- Mitigation: parse → show extracted transactions in a confirm UI → user approves → ingest. NOT auto-ingest.

**Part C — Per-month edit UI (the scope creep):**
- Users editing transactions in the UI requires `PATCH /transactions/:id`, `DELETE /transactions/:id`, optionally `POST /transactions`.
- This is a real CRUD UI with date pickers, category dropdowns, optimistic updates.
- Effort: 6-8h frontend + 2-3h backend + tests. **Too much for the remaining window.**

**Scope (minimum for demo):**
- **Ship Part A only.** CSV upload from chat → existing `/ingest/csv` → success toast → dashboard refresh.
- **Defer Part B (PDF parse).** Note in backlog as "post-hackathon — needs confirmation UX to be safe."
- **Defer Part C (edit UI).** Note as "post-hackathon — judges don't need to edit, they need to see analysis."

**Files to touch (Part A only):** `frontend/app/api/ingest/csv/route.ts` (NEW Vercel proxy), `frontend/components/chat/upload-button.tsx` (NEW file picker + multipart POST), `frontend/app/chat/page.tsx` (mount upload button + render system message on success).

**Effort:** 2-3h (Part A only).
**Owner:** TBD — @mahyar to discuss with team after V1+V2 land. Skip if the team is at capacity; pitch isn't blocked on this.
**Demo value:** HIGH — "bring your own data" is the difference between toy demo and real product.
**Risk:** LOW for Part A (existing backend works). HIGH for Part B if we tried it.
**AC:**
- [ ] `+ Upload statement` button visible in chat composer.
- [ ] Selecting a CSV file with `date,merchant,category,amount,currency` columns → POST to backend → success.
- [ ] Chat shows "Ingested 28 transactions" system message.
- [ ] Dashboard reflects the new data on refresh.
- [ ] Bad CSV format returns a clean error in chat, not a crash.

**Recommendation:** **ship-if-time** — Part A is high-leverage. PDF parse explicitly **defer**: not worth the demo-day risk.

---

### Vision-backlog overall recommendation

With ~5 days to submission and today already burned on a marathon bug-fix:

| Priority | Item | Why |
|---|---|---|
| 1 | **V2 dashboard polish** | @aidin frontend + @mahyar backend; biggest visual delta |
| 2 | **V1 goals (write + list + dashboard widget)** | @mahyar full stack; closes slide-7's dead beat |
| ✅ | ~~V3 memory delete~~ | **DONE 2026-06-06 EOD** — soft-delete + confidence-gated single-turn; live-verified on Atlas (visible 1→0, soft-deleted 0→1) |
| 3 | V4 Part A CSV upload | Team discussion after V1+V2 land |

**Skip in this window:** V4 Part B (PDF parse) — risk > value at hackathon scope. V4 Part C (edit UI) — not what the pitch is about. Note both as post-hackathon roadmap, not as scoped items.

