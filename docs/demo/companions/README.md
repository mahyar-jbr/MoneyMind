# Companion HTML pages

These three pages get screen-recorded and dropped into the video at specific moments. See `SCRIPT.md` scenes 8 and 9 for when.

| File | Used in | Plays for |
|------|---------|-----------|
| `architecture.html` | Scene 8 | 16 seconds |
| `tools.html` | Scene 9 | 12 seconds |
| `memory-loop.html` | OPTIONAL — fallback for scene 5 if chat footage is weak | 14 seconds |

## How to record one

1. Open the file in **Chrome**. (Other browsers may render fonts slightly off.)
2. Press `F11` for full-screen.
3. Move the cursor to a corner so it's off-screen.
4. Start screen recording (1080p, 60fps if available).
5. Press `R` on the keyboard to restart the animation.
6. Let the animation play out (16 / 12 / 14 seconds depending on file).
7. Hold for 2 more seconds after the final state lights up.
8. Stop recording.

That's it. Each page auto-plays on load, but `R` resets to T=0 so you have a clean take.

## What each shows

### architecture.html — the request flow

Five layers light up left to right with emerald arrows connecting them:

1. **Browser** (Next.js + Tailwind)
2. **Vercel** (the /api/chat edge proxy)
3. **FastAPI** (the backend on Railway)
4. **LangGraph Agent** (Gemini 2.5 Flash) — with all 18 tool pills lighting up inside the node
5. **MongoDB Atlas** — with the 4 jobs it does (ledger, vector memory, LangGraph state, MCP read tools)

Ends with a callout strip: *"Single event loop end-to-end · ~3s warm · <8s cold"*

### tools.html — the 18-tool catalog

6 group cards in a 3×2 grid:

- **Memory** (emerald) — recall, write, forget
- **Goals** (blue) — write_goal, list_goals, abandon_goal, check_goal_pace
- **Budgets** (amber) — set, list, abandon
- **Interventions** (pink) — propose, respond, log_outcome
- **Analytics** (purple) — query_transactions, get_spend_anomaly, summarize_week
- **Context & Crons** (slate) — update_user_context, schedule_reminder

Each group fades in with its accent color, then individual tool cards reveal in cascading waves.

Footer: *"94/94 backend tests · 222+ agent tests · + MongoDB MCP Server read tools"*

### memory-loop.html — OPTIONAL backup for scene 5

Three columns:

1. **User** — two timestamped chat bubbles ("May 4: I'm bulking", "May 31: how was my food spend?")
2. **MongoDB Atlas** — the actual memory document with full JSON schema (user_id, type, tag, summary, confidence, embedding [1024 dims], created_at, deleted_at)
3. **Agent** — the recall-laden reply citing the bulking context

Use this ONLY if the live chat footage from scenes 4-5 ends up weak (slow agent, awkward cursor, etc.). If the real chat takes are clean, skip this one.

## Brand colors used

Matches the existing pitch deck exactly:

| Use | Hex |
|-----|-----|
| Background | `#09090b` |
| Card surface | `#18181b` |
| Border | `#27272a` |
| Body text | `#e4e4e7` |
| Muted text | `#a1a1aa` |
| Emerald accent (the brand color) | `#34d399` |

If the editor needs to color-grade the rest of the screen footage to match, those are the hex values.

## If a number is wrong

The pages have a few hard-coded numbers:
- "18 native tools" (architecture.html + tools.html)
- "1024-dim cosine" (memory-loop.html)
- "94/94 backend tests · 222+ agent tests" (tools.html footer)
- "~3s warm · <8s cold" (architecture.html callout)

If any of these are out of date by the time you record, open the file in a text editor, find the number, change it, save, refresh Chrome. No build step. No framework.
