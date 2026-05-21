# Daily Standup

> Async standups. Update your section **once per day** (end-of-day is best). Read the others' sections before you start work the next morning.

## How to use this file

1. At end of day, scroll to today's date (or create it if it doesn't exist).
2. Add a 3-line entry under your name:
   - **Did:** what you actually finished
   - **Doing:** what you're on tomorrow
   - **Blocked:** anything you need from a teammate (or "nothing")
3. Commit with `chore(standup): YYYY-MM-DD @username`.
4. Push.

## Rules

- **3 lines max per person per day.** Longer = it's a doc, not a standup.
- **No status theater.** "Worked on backend" is useless. "Wrote CSV ingest endpoint, tested with 6mo synthetic data" is useful.
- **If you're blocked, say it loud.** A blocker is a teammate's problem to solve, not yours to suffer with quietly.
- **No standup = assumed blocked.** If a teammate skips a day, ping them.
- **Reference backlog items by #.** "Done with #4" is clearer than "finished the ingest thing."

## Template (copy this when adding a new day)

```markdown
## YYYY-MM-DD (Day X of sprint Y)

### @mahyar
- **Did:**
- **Doing:**
- **Blocked:**

### @kasra
- **Did:**
- **Doing:**
- **Blocked:**

### @aidin
- **Did:**
- **Doing:**
- **Blocked:**
```

---

# Sprint 1 — Foundations (May 21 → May 26)

## 2026-05-21 (Day 1 of Sprint 1)

### @mahyar
- **Did:** Atlas cluster provisioned (M0, us-east-1), `moneymind` DB + `memories` collection + vector index `memories_vector_idx` (1024 dim, cosine) ready. Gemini, Voyage, Clerk keys generated and in shared Doc. Repo skeleton pushed: README, BACKLOG, docs/, CLAUDE.md, CLAUDE.DEV.md.
- **Doing:** Writing first dev tickets — collection schemas (#2) and LangGraph minimum loop (#9).
- **Blocked:** Nothing.

### @kasra
- **Did:** _Onboarding — clone repo, copy values from shared Doc into `.env`, read README + BACKLOG + docs/setup.md._
- **Doing:**
- **Blocked:**

### @aidin
- **Did:** _Onboarding — clone repo, copy values from shared Doc into `.env`, read README + BACKLOG + docs/setup.md._
- **Doing:**
- **Blocked:**

---

<!--
Add new days below this line. Most recent at top, older below.
Keep all of Sprint 1 in this file. When Sprint 2 starts, add a new
`# Sprint 2 — The Agent (May 27 → Jun 2)` header above the old days.
-->
