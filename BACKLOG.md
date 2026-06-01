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
| 16  | Tool: `check_goal_pace(goal_id)`                              | @mahyar  | S    | Returns +/- pace vs. target             |
| 17  | Tool: `propose_intervention(type, params)` (awaits user OK)   | @mahyar  | M    | Approval UI fires + writes intervention |
| 18  | Tool: `log_outcome(intervention_id, result)`                  | @mahyar  | S    | Outcome tracked in `outcomes`           |
| 19  | Tool: `schedule_reminder(when, what)`                         | @mahyar  | S    | Reminder fires on schedule              |
| 20  | Tool: `summarize_week()`                                      | @mahyar  | M    | Weekly paragraph generated              |
| 21  | Weekly cron: triggers agent, posts to user inbox              | @kasra   | M    | Runs Sundays 8am, message lands         |
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

## Follow-ups added during Sprint 1 review

| #   | Status | Item                                                                | Owner    | Size | Why                                                  |
| --- | ------ | ------------------------------------------------------------------- | -------- | ---- | ---------------------------------------------------- |
| 4a  | ⬜ todo | Replace query/form `user_id` with Clerk JWT → `user_id` resolution across **all** routes (`/ingest/csv`, `/agg/weekly`, `/transactions`, future) | @kasra   | M    | Surfaced PR #2 + PR #3. Now blocks #21 cron AND every new route. Treat as a shared dependency, not a one-off. |
| 4b  | ✅ done (2026-05-21) | Decide CSV idempotency: re-upload same day = overwrite or append?  | @mahyar  | S    | Decided: **overwrite**. Logged in `docs/decisions.md`. |
| 9a  | ⬜ todo | Agent service: verify Clerk JWT on `POST /chat` (parallel to #4a)   | @mahyar  | S    | Surfaced reviewing #9. Blocked on #7 (Clerk scaffold). |
| 9b  | 🧊 post-freeze | Agent boot ergonomics: revisit package install pattern so `PYTHONPATH=..` is no longer required | @mahyar  | S    | Surfaced reviewing #9. Tried hatchling `[build-system]` install; pytest hung. Working state uses `PYTHONPATH=..` per `agent/README.md`. Not Sprint scope. |
| 6a  | ⬜ todo | Seed script: pipe `data/synthetic.csv` → `POST /ingest/csv` (one-shot `make seed`) | @kasra | S | Surfaced reviewing #6. Removes a manual step from every dev's onboarding. |
| 8a  | ✅ done (2026-05-27) | Replace `/api/chat` echo with proxy to backend `/chat` (Next.js route → FastAPI) | @aidin + @kasra | S | Closed by #10. Echo handler gone; `route.ts` is a transparent pass-through to `BACKEND_URL/chat`. |
| 7a  | ⬜ todo | Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY` to `.env.example` | @aidin | S | Surfaced reviewing #7. Clerk ran keyless locally, so no env vars landed — next dev to pull can't run the frontend. Onboarding blocker. |
| 8b  | ✅ done (2026-05-27) | **Lock the chat wire format.** Decide SSE vs. text/plain and document it in `docs/architecture.md` § "Chat wire format". All three legs (`chat-stream.ts`, `/api/chat` proxy, agent `/chat` output) must agree. | @mahyar | S | Decided plain-text chunked (not SSE), logged in decisions.md, documented in architecture.md. Proven live in #10 across all 3 legs. |
| 11a | ⬜ todo | **Agent graph migration to `create_react_agent`** — replace the hand-built `respond` node + the dead `_fetch_weekly_context` HTTP loop with a LangGraph prebuilt ReAct agent that takes the tool list as input. Batch-wires #11, #12, #13, #14, #15, #16, #17, #18, #19, #20 in one pass. | @mahyar | M | Surfaced reviewing #11. Decision: wire tools in batches, not per-tool, so the graph shape is decided ONCE. Run after 3-4 tools land (target: after #14). The current `_fetch_weekly_context` becomes dead code once this lands — flagged by dev report. |
| 11b | 🚨 **DEMO BLOCKER** | **Data hygiene: deduplicate transactions in Atlas + fix source-key collision.** `u_482` currently has every row twice because two ingests landed under the same `source` string today; the "overwrite on duplicate source" rule either didn't fire or the sources weren't actually identical. Investigate, dedupe, and tighten the source key (e.g. include user_id + timestamp bucket) so re-ingests can't accidentally double-write. | @kasra | S | Promoted to BLOCKER 2026-05-31: #12 demo numbers are 2× inflated on live Atlas (current=$422.42 instead of $211.21). Ratios survive scaling so `is_anomaly` is correct, but absolute dollar amounts in the demo paragraph won't match the CSV anyone can audit. CANNOT record the demo video against doubled data. |
| 11c | ⬜ todo | **Convention: agent tools take an injected `collection=None` kwarg.** Document the pattern in `docs/architecture.md` § "Agent tool conventions" (new section). Reason: tests can pass a mongomock-motor fake without monkeypatching globals — proven in #11 (12 tests run in <1s vs ~30s/run against Atlas). Apply to every tool #12-#20. | @mahyar | S | Surfaced in #11 dev report. One paragraph of docs; sets the pattern for the whole Sprint 2 tool series. |
| 12a | ⚠️ **6 reports in a row** | **Delete `backend/app/api/chat 2.py` + add Finder/iCloud duplicate patterns to `.gitignore`.** The file is byte-identical to `chat.py` (Finder/iCloud auto-duplicated on May 31). Untracked today, but one careless `git add -A` and it ships. Add patterns: `* 2.py`, `* 2.ts`, `* 2.tsx`, `* 2.json`, etc. | @kasra | S | Surfaced in #12. Flagged AGAIN in #13, #14, #14a, #15 dev reports. Five-minute fix; the noise floor it adds to every report is now genuinely corrosive. Mahyar: ping Kasra directly. |
| 3a  | ⬜ todo | **Decide: configure Atlas auto-embed on `memories`, OR document that writers embed themselves.** The vector index exists and works (proven in #13), but auto-embed is NOT configured on a source field — a doc inserted without an `embedding` field stays unindexed. #13 worked around with `embed_document()`; #14 (write_memory) will need to do the same. Either turn on auto-embed in Atlas UI (`summary` field is the natural source) OR update `docs/architecture.md` § "Layer 3" and `docs/data-model.md` § memories to say "writers populate `embedding` themselves via `voyage.embed_document()`." | @mahyar | S | Surfaced in #13 dev report. Cluster says READY since #3, but the auto-embed half was never set up. #14 must match whatever this decides — write THIS BEFORE drafting #14, or live with the workaround. |
| 13a | ⬜ todo | **Tool: `mark_memory_used(memory_id)`** — bumps `last_used` and increments `use_count` on a memory the agent has actually CONSUMED in a reply (not just retrieved). Separate from #13 so retrieval and consumption can diverge. Likely called at the end of the agent's response node when a recall genuinely influenced the output. | @mahyar | S | Deliberately deferred from #13 (read tool shouldn't write). Data-model docs imply the bump but don't say who does it. |
| 13b | ⬜ todo | **Voyage rate-limit hardening.** Free tier is ~3 RPM; dev hit a 5-min wait during #13 verification. Options: (a) upgrade Voyage account, (b) batch embeds (Voyage supports up to 128 inputs per call), (c) longer/jittered backoff than the current 1s+1retry. Decide before #21 cron lands — cron will embed N memories per active user per week and a single 429 cascade could brick the run. | @mahyar | S | Surfaced in #13. Reinforced in #14: single write+recall round-trip needed a 20s manual gap to clear rate limit on first attempt. Anything that writes >1 memory in a short window will need real batching, not just a longer sleep. |
| 14a | ✅ done (2026-06-01) | **Consolidate test fakes into `agent/tests/_fakes.py`.** Four distinct hermetic-testing patterns now exist across the agent tool suite: mongomock-motor (#11/#12), FakeCollection-that-trips-on-writes (#13), fake embedder (#13/#14), and `get_database` tripwire (#14). The tripwire pattern in particular is worth promoting — much stronger than "assert no extra rows." Extract them so #15-#20 don't reinvent. | @mahyar | S | LANDED. Pure refactor — 73/73 byte-equivalent, grep proves zero inline duplication remains, suite stayed at 1.12s. Two deliberately deferred ideas (`seed_memory_doc`, `FakeVoyageClient`) named in the dev report — if either shows up in #15-#20, extract then. |

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
