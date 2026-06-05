# MoneyMind — Product Backlog

**Code freeze:** 2026-06-04 (Thursday) · **Submission:** 2026-06-11 @ 2:00 PM PT

---

## 🚨 RULES-COMPLIANCE WORK (research complete 2026-06-05)

> Deep research pass complete. **R3 verdict: PERMISSIVE (~85% confidence)** — Google ships their own LangGraph template for Agent Builder, so the current stack does NOT need a reasoning-layer rewrite. R5 + R6 confirmed easier than expected. R7 Voyage flips to "keep with README disclosure" (Voyage is listed as an official MongoDB-track resource on the hackathon's own page). Net dev work under permissive: **~12-16 hours**.
>
> Full research doc with verbatim rule citations, GCP setup steps, and source URLs lives in chat — paste to eng tab when starting any of these.

### Do tonight — free wins, ~45 min total

| # | Status | Item | Owner | Size |
| --- | ------ | ---- | ----- | ---- |
| R5 | ⬜ **do now** | **MIT LICENSE at repo root.** Copyright line names Mahyar + Kasra + Aidin. GitHub auto-detects + shows in About sidebar. | @mahyar | XS (5min) |
| R6 | ✅ **PASSES — close** | Originality: first commit 2026-05-21, contest started 2026-05-05. **16 days inside window. No remediation.** Verified via `git log --reverse`. | @mahyar | DONE |
| R3-confirm | ⬜ **do now** | **Post R3 disambiguation question** to Devpost discussion forum + hackathon Discord. Phrasing template in research doc. Insurance against the 15% strict-reading risk; organizer answer arrives <24h. | @mahyar | XS (10min) |
| R8 | ⬜ **do now** | **Start Devpost draft submission**, walk every field, screenshot the form schema, save draft. Send team-member invites tonight so nobody's locked out 4pm Jun 11. | @mahyar | XS (30-45min) |

### Do tomorrow — mandatory pre-submission

| # | Status | Item | Owner | Size |
| --- | ------ | ---- | ----- | ---- |
| R1 | 🚨 **MANDATORY** | **Wire MongoDB MCP Server.** Subprocess (`npx mongodb-mcp-server@latest --read-only --connectionString $MONGODB_URI`) via `langchain-mcp-adapters` `MultiServerMCPClient`. Surface `aggregate` + `collection-schema` MCP tools into existing `create_react_agent(tools=[...])` list. Demo turn: "what does my data look like?" → agent calls `collection-schema` on transactions. **Read-only mode non-negotiable.** Dockerfile needs Node 20.19+ alongside Python. README must name it. | @mahyar | M (4-6h) |
| R2 | 🚨 **MANDATORY** | **Migrate to Vertex AI.** `pip uninstall langchain-google-genai && pip install langchain-google-vertexai`. Swap `ChatGoogleGenerativeAI` → `ChatVertexAI(model="gemini-2.5-flash", project=..., location="us-central1")`. GCP project + service account + `roles/aiplatform.user` + JSON key. Env vars: `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`. Remove `GOOGLE_API_KEY`. **$300 free trial covers entire demo** ($0.30/$2.50 per 1M tokens). | @mahyar | S (2-4h) |
| R4 | 🚨 **MANDATORY** | **Live hosted URL** at submission. Vercel for frontend + Railway for backend+agent (custom Dockerfile with Node + Python for MCP subprocess). Keep both up through mid-July 2026 (judging window). Clerk prod keys, prod env vars, prod smoke test. | @mahyar | M (3-4h) |
| R9 | ⬜ **scope shift** | **Demo video: re-target 2:00-2:30, not 90s.** Cap is 3 min; 90s was self-imposed. Extra ~60-90s = room for MCP-tool-firing-on-camera (eligibility proof), vector recall, intervention + outcome round-trip, memory-write-then-surface beat. Tell @kasra + videographer team. | @kasra | XS scope-shift |

### Confirmed safe — close & forget

- **R7 Voyage AI: KEEP.** Voyage is on hackathon's own MongoDB-track resources page (`rapid-agent.devpost.com/details/mongodb-resources`). One-line README disclosure citing that URL is the entire fix. **Saves 4-6h of vector-index rebuild.**
- **R10 Dep audit:** under PERMISSIVE, only R1+R2 dep changes needed. LangGraph, Voyage, Clerk, MongoDB Atlas, Next.js, FastAPI all safe.

### If R3 disambiguation returns STRICT (insurance plan, do NOT pre-emptively start)

Re-opens R7 (Voyage → Vertex embedding, 4-6h, full vector reindex) + adds LangGraph → ADK port (~1 day). Tight but doable in 5 days **only if** the strict ruling lands before Saturday morning. Track the R3-confirm response actively this weekend.

---

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
| 22  | ✅ done (2026-06-02) Intervention approval card                  | @aidin   | M    | LANDED (PR #45 merged, R3). Three-state card (pending / modify / resolved) drops into chat thread after each turn. Day-of-week picker for reminders, Framer Motion entrance, premium accent styling. Types match #17 `propose_intervention` shape. **Mock-only**: `fetchPending` + `respondTo` are stubs returning one hardcoded reminder after the first message — agent's actual #17/#17a Atlas writes are invisible to the UI. Real backend tracked as **#22a** (demo-decision needed). |
| 23  | ✅ done (2026-06-02) Dashboard page                              | @aidin   | L    | LANDED (PR #43 merged, R3). `/dashboard` reads live data via two new Clerk-gated proxy routes (`/api/agg/weekly`, `/api/transactions`). StatCards (total / this week / top category / txn count) + hand-rolled SVG SpendChart + CategoryBreakdown + TransactionsList. Loading skeleton, error state, empty state. 9 new lib files isolate formatters + aggregations for testability. New env var precedence `BACKEND_URL > NEXT_PUBLIC_BACKEND_URL > default`. **Strongest visual beat for the demo video.** Goals + memories widgets deferred to follow-up (blocked on backend endpoints); `/inbox` rendering tracked as #23a. |

**Sprint 2 demo (Jun 2):** The slide-8 scenario, working live. Agent notices food spike → asks → user replies → memory writes → confirmation.

---

## Sprint 3 — Polish (Jun 3 → Jun 4) · CODE FREEZE Jun 4 EOD

> **Goal:** two days. No new features. Voice, motion, demo video, Devpost. If item #27 (the video) is at risk, kill anything else.

| #   | Item                                                                  | Owner            | Size | Demo proof                       |
| --- | --------------------------------------------------------------------- | ---------------- | ---- | -------------------------------- |
| 25  | Agent voice tuning (prompt iteration on 10 scenarios) — see notes below for 4 concrete targets | @mahyar | M | Reads warm + concrete, not robotic |
| 26  | Frontend animations + visual polish (pitch-deck quality)              | @aidin           | M    | Feels premium on first 5 sec     |
| 27  | **Demo video — script, record, edit (90s max)** — Kasra coordinating with videographer team | @kasra | L | `demo.mp4` in repo |
| 28  | Devpost writeup (cribbed from pitch deck + README)                    | @mahyar          | M    | Draft submitted, link in repo    |
| 29  | Smoke test full flow on the LIVE deployed URL (post-R4) with fresh user | all | S | No errors, no console warnings on prod |
| 30  | Tag `v1.0` and freeze main branch                                     | @mahyar          | S    | Tag pushed, branch protected     |

**#25 tuning targets** (concrete iteration list, verified against live demo transcripts):

(a) When `summarize_week` returns `total_spend=0` AND recent goal data exists, prompt should nudge Gemini to either retry with `week_offset=-1` OR explicitly say "no data this calendar week, here's last week." Today Gemini's reply says "you haven't recorded any spending this week" — true but unhelpful. **Verified still open 2026-06-03:** the CSV's last week is 2026-05-18-24, dedup didn't extend the date range, so "this week" (Jun 1-7) is still empty.
(b) When `active_context_block` is injected into the system message, prompt should reference it explicitly in the reply. Wiring proved correct in `#11a` (active context retrievable end-to-end), but Gemini ignored it on Turn 3.
(c) `summarize_week`'s paragraph template is rigid v1. Once we have 10 real weekly digests on real data, soften the deterministic phrasing without losing the whole-dollar / no-markdown contract.
(d) Empirical from `#17a-wire` live demo: when the user says "I want a Sunday reminder," Gemini described it in prose instead of calling `propose_intervention`. Teach the LLM: (i) on commitment to a proposal, CALL the tool, THEN paraphrase; (ii) on user's response turn, call `respond_to_intervention` BEFORE writing memory; (iii) only `write_memory` if confidence > 0.5 AND ≥2 evidence pieces.

**Primitive to use:** `agent/scripts/demo_graph_full.py` records which tools Gemini picks per turn — that's the feedback loop. Avoid burning the 20/day Gemini quota on speculative tuning; budget ~8 takes for #25, save the rest for #27 recording.

---

## Open follow-ups

> Done items have been pruned. If it's not here, it's either complete or out of scope.

| #   | Status | Item                                                                | Owner    | Size | Why                                                  |
| --- | ------ | ------------------------------------------------------------------- | -------- | ---- | ---------------------------------------------------- |
| 22a-swap | 🚨 **demo-critical** | **Aidin swaps the two mock seams in `frontend/lib/interventions.ts`** for real `fetch()` calls to `/api/interventions/pending` and `/api/interventions/{id}/respond`. Add matching proxy routes under `frontend/app/api/interventions/` (Clerk-bearer-forward, same pattern as `/api/transactions`). Smoke-test against real agent writes via chat. | @aidin | XS | Slide-8 card is still mock theater until this lands. Blocks #27 recording. |
| 23a-seed | 🟡 **before recording** | **Trigger `/agent/run-weekly-summary` + `/agent/run-reminders` against the demo user** so the inbox has populated content on camera. POST both endpoints once before each take. | @mahyar | XS | 30 seconds of curl per take. |

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
| **Rules-compliance disqualification**         | **Critical** | **R1-R10 above must all close before submission.** MCP integration revival (R1), Vertex AI migration (R2), Agent Builder verification (R3) are the three load-bearing ones. PM missed this audit at sprint start — caught 2026-06-03. |
| Vector search latency too high                | Low        | Cache top-k recalls per user · pre-embed on write      |
| Gemini free-tier 20 req/day during demo       | **High**   | **Pre-record fallback IS the plan, not the backup** — ration takes: ~8 for #25 voice tuning, rest for #27 recording. Decided 2026-06-02 to stay free-tier through demo. **Will be re-decided after R2** — Vertex AI billing changes the equation. |
| Synthetic dataset feels fake on camera        | High       | @kasra spends extra time on realistic patterns wk 1    |
| Demo video runs over 90s                      | High       | Storyboard before recording · cut one beat if needed   |
| One teammate gets sick / disappears 48h       | Low        | Each swim lane shippable independently (see slide 14)  |
