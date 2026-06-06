# MoneyMind — Product Backlog

**Code freeze:** 2026-06-04 (Thursday) · **Submission:** 2026-06-11 @ 2:00 PM PT

---

## 🚨 RULES-COMPLIANCE

> Execution order matters: R2 swaps the LLM layer (changes pyproject.toml). R4 builds the Dockerfile (consumes pyproject.toml + adds Node for R1). R1 wires the MCP subprocess (needs Node + the final LLM layer). R8 + R9 are independent and can run any time.

| # | Item | Owner | Size |
| --- | ---- | ----- | ---- |
| R2 | ✅ **done 2026-06-05** — Vertex AI migration verified live in PROD. `moneymind-agent@moneymind-hack.iam` SA, `roles/aiplatform.user`, key as `GOOGLE_APPLICATION_CREDENTIALS_JSON_B64` (base64 — raw JSON corrupted PEM newlines). Import fix: `langchain_google_vertexai.chat_models` submodule (cold-import 236s → 2.1s). 222 tests, ruff clean. | @mahyar | — |
| R4 | ✅ **done 2026-06-05** — Live URLs: frontend https://money-mind-seven.vercel.app (Vercel, Next 15) + backend+agent https://moneymind-production-2a7e.up.railway.app (Railway, single Docker container). End-to-end verified: Clerk sign-in → dashboard renders $17,380/26-weeks → chat returns live Vertex Gemini reply. | @mahyar | — |
| R-budget | ⚠️ **before recording** | **GCP budget alert** — https://console.cloud.google.com/billing/budgets → Create Budget scoped to `moneymind-hack`, $300, alerts at 50/90/100%. Confirm account flagged "Free trial" not "Paid". Optional Layer 3: disable billing post-submission (June 12) as hard kill switch. Billing page sometimes fails to load — retry tomorrow if so. | @mahyar | XS (5 min) |
| R1 | ✅ **done 2026-06-06** — MongoDB MCP server wired as first-class tool source. `agent/mcp_integration/client.py` lazy-spawns `npx mongodb-mcp-server@latest --read-only` on first `get_mcp_tools()`; MCP tools get `mongo_` prefix and join the 11 native tools in `create_react_agent(tools=)`. `_build_tools` + `build_graph` are now async (cascaded through `arun_chat`, `stream_chat`, 14 test_graph callsites). `--read-only` hardcoded + enforced by `test_server_config_includes_read_only_flag`. Graceful fallback: spawn failure returns `[]`, agent still boots with 11 native tools (verified by an unrelated import collision that forced rename `agent/mcp/` → `agent/mcp_integration/` to dodge upstream `mcp` package). 232 → 242 tests; conftest.py autouse stubs `get_mcp_tools` to `[]` in graph tests. README + system prompt updated. **Awaiting live verification on prod URL** — schema-meta question should fire a `mongo_*` tool. | @mahyar | — |
| R8 | **Devpost draft** — walk form, save draft, send team invites. Independent of R1/R2/R4. | @mahyar | XS |
| R9 | **Demo video: target 2:00-2:30**, not 90s. Cap is 3 min. Extra time = MCP-firing-on-camera + vector recall + intervention loop + memory beat. Independent. | @kasra | XS |

**Dependency chain:** R2 changes `agent/pyproject.toml`. R4's Dockerfile installs that pyproject. R1's MCP integration needs both the final Python env (from R2) AND the Node runtime added in R4. R8 + R9 have no dependencies. Doing R1 before R2 means building MCP integration against the wrong LLM layer; doing R4 before R2 means a rebuild of the Docker image. **Execute as R2 → R4 → R1.**

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
| 25  | Agent voice tuning (in progress on branch `25`)                       | @mahyar          | M    |
| 26  | Frontend dashboard + chat polish                                      | @aidin           | M    |
| 27  | **Demo video — script, record, edit (2:00-2:30, max 3min)**           | @kasra           | L    |
| 28  | Devpost writeup (full prose, replaces the placeholder draft)          | @mahyar          | M    |
| 29  | Smoke test full flow on live deployed URL with fresh user             | all              | S    |
| 30  | Tag `v1.0` and freeze main                                            | @mahyar          | S    |

---

## Open follow-ups

> Done items have been pruned. If it's not here, it's either complete or out of scope.

| #   | Status | Item                                                                | Owner    | Size | Why                                                  |
| --- | ------ | ------------------------------------------------------------------- | -------- | ---- | ---------------------------------------------------- |
| 22a-swap | 🚨 **demo-critical** | **Aidin swaps the two mock seams in `frontend/lib/interventions.ts`** for real `fetch()` calls to `/api/interventions/pending` and `/api/interventions/{id}/respond`. Add matching proxy routes under `frontend/app/api/interventions/` (Clerk-bearer-forward, same pattern as `/api/transactions`). Smoke-test against real agent writes via chat. | @aidin | XS | Slide-8 card is still mock theater until this lands. Blocks #27 recording. |
| 23a-seed | 🟡 **before recording** | **Trigger `/agent/run-weekly-summary` + `/agent/run-reminders` against the demo user** so the inbox has populated content on camera. POST both endpoints once before each take. | @mahyar | XS | 30 seconds of curl per take. |

