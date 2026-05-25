# MoneyMind — Product Backlog

**Code freeze:** 2026-06-04 (Thursday) · **Submission:** 2026-06-11

## Legend

- **Status:** `⬜ todo` · `🟡 wip` · `✅ done (YYYY-MM-DD)` · `🚧 blocked`
- **Size:** `S` = ½ day · `M` = 1 day · `L` = 2 days · `XL` = 3+ days
- **Owner:** `@mahyar` (agent) · `@kasra` (backend) · `@aidin` (frontend)
- **Demo proof:** if this lands, this is what shows up in the demo video. If you can't name a demo proof, the item is busywork — cut it.

## Rules

1. **Nothing leaves the backlog without a demo proof.** If it won't appear in the 90-second video or the live walkthrough, it doesn't ship.
2. **Update status in the daily standup.** `todo → wip → done → blocked`.
3. **Owners are locks, not suggestions.** If you're stuck, escalate before the end of the day — don't silently fall behind.
4. **Out-of-scope items stay out.** New ideas after Sprint 1 go to `## Won't ship`, not to the top of the list.

---

## Sprint 1 — Foundations (May 21 → May 26)

> **Goal:** end-to-end walking skeleton. Push a CSV in, get an agent paragraph out. Schemas locked, contracts agreed.

| #   | Status | Item                                                                                                       | Owner    | Size | Demo proof                              |
| --- | ------ | ---------------------------------------------------------------------------------------------------------- | -------- | ---- | --------------------------------------- |
| 1   | ✅ done (2026-05-21) | Atlas cluster + IAM + connection string in `.env.example`                                | @mahyar  | S    | M0 cluster `moneymind` live in us-east-1, user `moneymind-app` created, network `0.0.0.0/0`, connection string in shared Doc |
| 2   | 🟡 wip | Collections: `transactions`, `goals`, `memories`, `interventions`, `outcomes`, `user_context`             | @mahyar  | M    | Schemas documented in `docs/data-model.md` ✅, code-side creation TBD via ticket |
| 3   | ✅ done (2026-05-21) | Vector index on `memories.embedding`                                                     | @mahyar  | M    | `memories_vector_idx` READY, 1024 dim cosine, filters on `user_id` + `type` |
| 4   | ✅ done (2026-05-21) | CSV ingest endpoint `POST /ingest/csv` → `transactions` collection                          | @kasra   | M    | PR #2 merged. All 3 blocking issues fixed across commits 7b68c20, 0e3cc7d, 5081cad. Awaits synthetic data (#6) to verify "6mo loads cleanly." |
| 5   | 🟡 wip | Aggregation: weekly spend by category                                                                     | @kasra   | S    | JSON returned from `/agg/weekly`. PR #3 in review (changes requested 2026-05-21) |
| 6   | ⬜ todo | Synthetic dataset generator (1 user, 6 months, realistic patterns)                                        | @kasra   | L    | `data/synthetic.csv` checked in         |
| 7   | ⬜ todo | Next.js scaffold + Clerk auth + dark theme tokens                                                         | @aidin   | M    | Sign in → empty dashboard               |
| 8   | ⬜ todo | Chat shell (streaming UI, no agent yet — echo backend)                                                    | @aidin   | M    | Type → tokens stream back               |
| 9   | ⬜ todo | LangGraph minimum: 1 node, Gemini call, returns a paragraph                                               | @mahyar  | M    | Hello-world loop runs locally           |
| 10  | ⬜ todo | Glue: frontend → `/chat` → agent → MongoDB read → response                                                | all      | M    | Walking skeleton — CSV → paragraph      |

**Bonus done today (2026-05-21):** Gemini, Voyage, and Clerk API keys provisioned + saved to shared Google Doc. Both teammates can run `cp .env.example .env`, paste values, and connect.

**Sprint 1 demo (May 26):** Walking skeleton. "Here's a CSV, here's an agent reply that references real numbers from it."

**Hard stop if not done:** if items 1–10 aren't all green by EOD May 26, replan before starting Sprint 2. Do not grind into Sprint 2 on a broken foundation.

---

## Sprint 2 — The Agent (May 27 → Jun 2)

> **Goal:** all 10 agent tools live, weekly cron loop, intervention approval flow. The slide-8 scenario works live.

| #   | Item                                                          | Owner    | Size | Demo proof                              |
| --- | ------------------------------------------------------------- | -------- | ---- | --------------------------------------- |
| 11  | Tool: `query_transactions(filters)`                           | @mahyar  | S    | Returns rows for given filter           |
| 12  | Tool: `get_spend_anomaly(category, window)`                   | @mahyar  | M    | Detects food spike in demo data         |
| 13  | Tool: `recall_memory(query, k=5)` via vector search           | @mahyar  | M    | Past context surfaces in agent reply    |
| 14  | Tool: `write_memory(type, evidence, confidence)`              | @mahyar  | S    | Doc appears in `atlas.memories`         |
| 15  | Tool: `update_user_context(text)` ("I'm bulking")             | @mahyar  | S    | Context stored + influences next reply  |
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
