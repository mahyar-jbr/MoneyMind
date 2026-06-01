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

## Open follow-ups

> Done items have been pruned. If it's not here, it's either complete or out of scope.

| #   | Status | Item                                                                | Owner    | Size | Why                                                  |
| --- | ------ | ------------------------------------------------------------------- | -------- | ---- | ---------------------------------------------------- |
| 11b | 🚨 **DEMO BLOCKER** | **Atlas dedup + source-key fix.** `u_482` rows are doubled on the demo cluster (`#12` reported `$422.42` vs. the auditable `$211.21`; `#11a` live demo confirmed 670 rows for u_demo_graph_11a instead of ~330). Verdicts survive scaling but absolute dollars in the demo paragraph won't match the CSV. Investigate the duplicate `source` collision, dedupe, tighten the source key. | @kasra | S | CANNOT record demo video until fixed. |
| 12a | ⚠️ **7 reports flagged** | **Delete `backend/app/api/chat 2.py` + add `* 2.*` patterns to `.gitignore`.** Byte-identical Finder duplicate. Untracked but one `git add -A` away from shipping. | @kasra | S | Mahyar: ping Kasra directly. |
| 4a  | ⬜ todo | **Clerk JWT → `user_id` resolution batch.** Replace required `user_id` query/form/path param with JWT-derived resolution across ALL routes (backend `/ingest/csv`, `/agg/weekly`, `/transactions`, `/chat` AND agent `/chat`). Folds the agent-side JWT verify into the same swap. | @kasra | M | Blocks #21 cron. Every new agent tool's route adds to the eventual swap. |
| 7a  | ⬜ todo | **Add Clerk keys to `.env.example`** (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY`). Clerk ran keyless locally during #7 so no env vars landed. Next dev to pull can't run the frontend. | @aidin | S | Onboarding blocker. |
| 6a  | ⬜ todo | **One-shot seed script** — `make seed` pipes `data/synthetic.csv` → `POST /ingest/csv`. Removes manual onboarding step. | @kasra | S | Quality-of-life, not blocking. |
| 13a | ⬜ todo | **Tool: `mark_memory_used(memory_id)`** — bumps `last_used` + `use_count` when the agent actually CONSUMES a recalled memory (not just retrieves). Deliberately split from #13 so read and consume can diverge. | @mahyar | S | Data-model implies the bump; this is who does it. |
| 13b | ⬜ todo | **Voyage rate-limit hardening.** Free tier ~3 RPM; #13 hit a 5-min wait, #14 needed a 20s manual gap on a single round-trip. Options: upgrade account, batch (up to 128 inputs/call), jittered backoff. Decide before #21 cron embeds N memories per user per week. | @mahyar | S | Single 429 cascade could brick the cron. |
| 25p | ⬜ todo | **Prompt-tuning targets surfaced by #11a's live demo** (folds into Sprint 3 #25). (a) When "this week" has no data, fall back to the most recent populated week (same semantics decision as #12). (b) When `active_context_block` is injected, reference it explicitly in the reply — wiring is provably correct but Gemini ignored it on the demo's Turn 3. | @mahyar | — | Not a separate Sprint 2 ticket; pre-loads #25's iteration list. |
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
