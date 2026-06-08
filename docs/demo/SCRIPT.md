# MoneyMind Demo Video — Production Script

**Total length:** 2:20 (10s of headroom before the 2:30 hard cap)
**Aspect:** 16:9, 1080p, 60fps if possible
**Tone:** confident, conversational. Not podcast-bro. Read it like you're explaining the product to a smart friend.

---

## Quick reference — the 10 scenes

| # | Time | Length | What it shows | One-liner voiceover |
|---|------|--------|---------------|---------------------|
| 1 | 0:00–0:08 | 8s | Cursor drags a real Amex PDF into the chat composer | "Most finance apps make you type in every transaction." |
| 2 | 0:08–0:30 | 22s | The 6-step import-progress card animates, then morphs into a $1,709.88 StatementCard | "MoneyMind reads it. Gemini extracts. Categorizes. Writes to MongoDB — in real time." |
| 3 | 0:30–0:42 | 12s | Dashboard fills with the real spend we just imported | "And now the agent knows the user's actual life." |
| 4 | 0:42–1:02 | 20s | Chat: "how was my spending this week" → reply. Then user says "I'm bulking this month" → agent acknowledges | "Most finance apps remember your transactions. MoneyMind remembers you." |
| 5 | 1:02–1:18 | 16s | Chat: "what do you remember about me?" → agent cites the bulking context | "The next day, the next month, the next conversation — that context comes back." |
| 6 | 1:18–1:38 | 20s | Cap intervention card appears, user clicks Modify, changes to $250, clicks Accept | "When MoneyMind sees a pattern worth acting on, it proposes — and the user stays in control." |
| 7 | 1:38–1:52 | 14s | Dashboard shows the new cap with the real spend bar against it. Chat: "what are my caps?" → agent reads it back | "The cap is alive. Saved to Atlas. The agent reads it back like it always knew." |
| 8 | 1:52–2:08 | 16s | Switch to `companions/architecture.html` recording | "Built on Gemini and Vertex AI. LangGraph orchestrates 18 native tools. One MongoDB Atlas cluster." |
| 9 | 2:08–2:20 | 12s | Switch to `companions/tools.html` recording | "Eighteen tools. The agent decides when to use each. The user just talks." |
| 10 | 2:20–2:30 | 10s | MoneyMind logo + tagline | "MoneyMind. Remember the person, not just the transactions." |

---

## Before you record anything — setup checklist

Do these once at the start of your recording session. They take ~10 minutes.

### 1. Wipe the demo account so the dashboard is blank

From the project root:
```bash
cd agent
PYTHONPATH=.. .venv/bin/python -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv('../.env')
from agent.db.client import get_database
USER = os.environ.get('CLERK_USER_ID') or 'user_3Ee1E3uB6IlBAy2geVeujnqAmjo'
async def main():
    db = get_database()
    for c in ['transactions','goals','budgets','memories','interventions','outcomes','user_context','reminders','inbox_messages']:
        r = await db[c].delete_many({'user_id': USER})
        if r.deleted_count: print(f'  {c}: -{r.deleted_count}')
asyncio.run(main())
"
```

Mahyar will give you the `CLERK_USER_ID` value if it's not in your `.env`.

### 2. Warm up Railway so the agent isn't cold

```bash
curl https://moneymind-production-2a7e.up.railway.app/health
```

Then **send one dummy chat message** in the live app (`money-mind-seven.vercel.app/chat`) so the graph is warmed. Without this, the first PDF upload will take 30+ seconds instead of 5-8. **Do this 30 seconds before each take.**

### 3. Pre-seed a cap intervention so scene 6 has something to click

```bash
cd agent
PYTHONPATH=.. .venv/bin/python -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv('../.env')
USER = os.environ.get('CLERK_USER_ID') or 'user_3Ee1E3uB6IlBAy2geVeujnqAmjo'
async def main():
    from agent.tools.propose_intervention import (
        ProposeInterventionInput, ProposeInterventionTrigger, propose_intervention,
    )
    r = await propose_intervention(ProposeInterventionInput(
        user_id=USER, type='cap',
        params={'category':'food','limit':300},
        triggered_by=ProposeInterventionTrigger(tool='get_spend_anomaly', input={'category':'food'}),
    ))
    print('intervention id:', r.intervention_id)
asyncio.run(main())
"
```

You don't have to wait for the agent to detect a spending pattern live — that's unreliable on camera. We seed the intervention before the recording so the card is already pending when we open the chat for scene 6.

### 4. Get your browser ready

- Chrome in **dark mode** (`chrome://settings` → appearance → device-based or dark)
- Window size **1440 × 900** (resize manually; don't use device toolbar)
- Hide bookmarks bar (`Cmd+Shift+B`)
- Turn off all browser notifications
- Sign into `money-mind-seven.vercel.app` and stay signed in
- **No Incognito** — cold loads are slower

### 5. Get screen recording ready

- Use **ScreenStudio** or **CleanShot X** if you have them (auto-zoom on click is the polish that separates demos)
- 1080p, 60fps if possible
- Cursor **visible** (the editor needs to see where the user interacts)

### 6. Stage the PDF for scene 1

Put `docs/Summary.pdf` somewhere easy to drag from — Finder window positioned on the LEFT half of the screen. Have `docs/Summary (1).pdf`, `(2).pdf`, `(3).pdf` as backups in case the first one parses weirdly.

---

## Scene-by-scene recording instructions

Each scene = one continuous screen recording (one `.mov` file). The editor cuts between them. Don't try to record everything in one take.

### Scene 1 & 2 — PDF drop + import animation

**Record one continuous take, ~32 seconds.**

1. Finder window with `Summary.pdf` on the left half of the screen.
2. Chat tab on the right half. Empty chat (just the welcome message).
3. Start recording. Wait 1 second.
4. **Click and drag** `Summary.pdf` over the paperclip icon in the chat composer. Drop it.
5. The import-progress card mounts. **Do not touch anything.** Let the 6-step animation play through naturally (5-8 seconds on a warm container).
6. When the card morphs into the StatementCard (showing **CA$1,709.88 across 69 transactions** with category bars), hold for 4 seconds.
7. Stop recording.

**Common failures:**
- The first run takes 30+ seconds because Railway is cold. Stop, warm it again (curl `/health`), retry.
- A transaction or two parsed weirdly. Acceptable — the $1,709.88 total is what matters on camera. Don't sweat 1-2 missing rows.

**Voiceover for this scene** (will be dubbed over by you / your VO):
> "Most finance apps make you type in every transaction. MoneyMind reads it. Gemini extracts every transaction, categorizes them, writes them to MongoDB — in real time. 69 transactions. Six and a half seconds."

**On-screen text overlays** the editor should add:
- At 0:22: lower-third **"Real PDF · Real Atlas · 6.4 seconds"** in emerald color matching the brand

---

### Scene 3 — Dashboard fill

**Record one continuous take, ~15 seconds.**

1. After scene 2 finishes, wait 2 seconds.
2. Click **Dashboard** in the nav.
3. The dashboard fetches and renders. **You'll see the KPIs populate, the Top Categories bars draw in left-to-right, the Monthly Spend chart appear.** This is the visual hook.
4. **Don't interact.** Cursor at rest in a neutral area.
5. Stop recording after ~12 seconds, once everything is fully drawn.

**Common failures:**
- Bars filled instantly because the fetch was cached. Hard-refresh (`Cmd+Shift+R`) and re-do.
- Cursor was hovering a bar and a tooltip appeared. Move cursor away first.

**Voiceover:**
> "And now the agent knows the user's actual life. Real spend. Real categories. From a real PDF."

**On-screen text:**
- Subtle **"Real spend. Real categories."** top-right corner, fade in/out

---

### Scene 4 — Chat exchange + context write

**Record one continuous take, ~25 seconds.**

1. Click **Chat** in the nav. Scroll to the bottom — the StatementCard from earlier should still be in the thread.
2. Start recording.
3. **Type at human pace, don't paste:**
   ```
   how was my spending this week
   ```
4. Hit Enter. Wait for the streamed reply to finish. Hold 2 seconds.
5. **Type:**
   ```
   I'm bulking this month, so I'm eating more
   ```
6. Hit Enter. Wait for reply (the agent should acknowledge + mention it'll remember). Hold 2 seconds.
7. Stop recording.

**Tip:** after typing each message, move the cursor AWAY from the textarea before the reply streams in. A blinking cursor inside the input while text streams elsewhere is distracting.

**Voiceover:**
> "Most finance apps remember your transactions. MoneyMind remembers you. Your patterns, your context, the things you only said once. 'I'm bulking this month.'"

**On-screen text overlays:**
- At 0:48 (right after the second message lands): small pill **"context written to Atlas"** in JetBrains Mono font, emerald accent. Fades in then out.

---

### Scene 5 — Agent recalls the bulking context

**Record one continuous take, ~15 seconds.**

Continuation of scene 4 — keep the same chat thread, same recording session.

1. Start recording.
2. **Type:**
   ```
   what do you remember about me?
   ```
3. Hit Enter. Wait for the reply (should mention bulking).
4. Hold the reply on screen for 3 seconds.
5. Stop recording.

**If the agent doesn't mention bulking:** scene 4's context write didn't fire. Re-do scene 4 with the more explicit prompt:
```
I'm bulking this month so my food spend will be higher — please remember that
```

**Voiceover:**
> "The next day, the next month, the next conversation — that context comes back. Vector recall over Voyage AI embeddings."

**On-screen text overlays:**
- At 1:08: small pill **"recall_memory · 1024-dim vector search"** in JetBrains Mono, emerald accent

---

### Scene 6 — Cap intervention with Modify

**Record one continuous take, ~25 seconds.**

**Prerequisite:** the cap intervention is pre-seeded in Atlas (setup step 3).

1. Refresh the chat page (`Cmd+R`) so the pending intervention loads.
2. The intervention card "Cap food at $300/month?" appears at the bottom. Scroll to it if it's not visible.
3. Start recording.
4. Hover over the **Modify** button. Don't click yet — let the cursor sit there for a second.
5. Click **Modify**. An input field appears showing **$300**.
6. Triple-click to select the value, type `250`. Tab or click out to confirm.
7. Click **Accept**.
8. The card collapses into a small "Cap saved" confirmation chip.
9. Hold for 2 seconds. Stop recording.

**Voiceover:**
> "When MoneyMind sees a pattern worth acting on, it proposes — and the user stays in control. Accept, decline, or modify. Here, modify to $250."

**On-screen text:**
- At 1:24: centered text **"Insight → Decision → Action"** fades in for 2 seconds then out

---

### Scene 7 — Cap appears on dashboard + agent reads it back

**Record one continuous take, ~16 seconds.**

1. After scene 6 finishes, click **Dashboard** in the nav.
2. The dashboard loads. The Budget Progress widget now shows **"Food $175 / $250"** with a real progress bar at ~70%.
3. Hold for 4 seconds.
4. Click back to **Chat**.
5. **Type:**
   ```
   what are my caps?
   ```
6. Hit Enter. Wait for reply (agent says food $250, ~70% used).
7. Hold reply for 3 seconds.
8. Stop recording.

**Voiceover:**
> "The cap is alive. Saved to Atlas. The agent reads it back like it always knew."

**On-screen text:**
- At 1:44: lower-third **"Atlas write → dashboard render: ~2 seconds"** in emerald

---

### Scene 8 — Architecture diagram (HTML page)

**Record one continuous take, ~18 seconds.**

1. Open `docs/demo/companions/architecture.html` in Chrome.
2. Press `F11` to go full-screen.
3. Move the cursor off the screen (top-right corner).
4. Start recording.
5. Press `R` to restart the animation cleanly.
6. Let the full 16-second animation play through. **Don't move the cursor.** Don't touch anything.
7. Hold the final frame for 2 more seconds.
8. Stop recording.

**What the animation does:** Browser → Vercel → FastAPI → LangGraph → Atlas lights up left-to-right with emerald arrows connecting them. Inside the LangGraph node, all 18 tool pills light up in waves. The Atlas node shows its 4 jobs (ledger, vector memory, LangGraph state, MCP read tools). A callout strip at the bottom appears at the end.

**Voiceover:**
> "Built on Gemini and Vertex AI for reasoning. LangGraph orchestrates 18 native agent tools. One MongoDB Atlas cluster holds the ledger, the vector memory, the agent's working state — and the MongoDB MCP Server lets the agent inspect the database when it needs to."

---

### Scene 9 — 18 tools catalog (HTML page)

**Record one continuous take, ~14 seconds.**

1. Open `docs/demo/companions/tools.html` in Chrome, `F11`.
2. Move cursor off-screen.
3. Start recording.
4. Press `R` to restart.
5. Let the 12-second animation play out — 6 groups fade in (Memory, Goals, Budgets, Interventions, Analytics, Context & Crons), then 18 individual tool cards reveal in cascading waves, each group with its own accent color.
6. Hold the final frame 2 more seconds.
7. Stop recording.

**Voiceover:**
> "Eighteen tools. The agent decides when to use each one. The user just talks."

---

### Scene 10 — Closing logo

**Either record a screen capture or build directly in the editor.**

- MoneyMind wordmark with emerald accent (same brand as the rest of the video)
- Fade in the wordmark over 1 second
- 1 second hold
- Tagline below fades in over 1 second: **"Remember the person, not just the transactions."**
- 3 second hold
- Fade out

**Voiceover:**
> "MoneyMind. Remember the person, not just the transactions."

---

## Audio direction

- **Music:** silent for the first 8 seconds (the PDF drop carries itself). Subtle ambient bed enters at 0:08 with the import animation. Slight swell at 1:18 (intervention card) and 1:52 (architecture cut). Fade to silence at 2:20 for the closing logo.
- **SFX:** keep minimal. One subtle "ding" when the cap is accepted (~1:34) and one when the budget materializes on the dashboard (~1:42). Nothing else.

---

## If the video runs over 2:30

Cut in this order:

1. **Scene 9 (tools.html, 12s)** — cut entirely or trim to 4s with a single sweep. Scene 8 already mentions the 18-tool number.
2. **Scene 5 (recall memory, 16s)** — trim to 8s by cutting straight to the agent reply.
3. **Scene 3 (dashboard fill, 12s)** — trim to 6s.

**Never cut:**
- Scenes 1-2 (PDF drop is THE magic moment)
- Scene 4 (the thesis statement)
- Scenes 6-7 (cap-accept loop)
- Scene 10 (logo)

---

## File output naming

Save each scene's recording as:
```
take-01-pdf-drop.mov          ← scenes 1+2 combined
take-02-dashboard-fill.mov    ← scene 3
take-03-chat-context.mov      ← scene 4
take-04-recall.mov            ← scene 5
take-05-intervention.mov      ← scene 6
take-06-cap-dashboard.mov     ← scene 7
take-07-architecture.mov      ← scene 8 (HTML)
take-08-tools.mov             ← scene 9 (HTML)
take-09-logo.mov              ← scene 10 (or build in editor)
```

Put them in a folder called `moneymind-demo-raw/` and share via Drive or Dropbox.

---

## When to re-shoot vs. when to accept

**Accept the take if:**
- Flow completes end-to-end without errors
- Text on screen is readable
- No browser notifications popped up
- No `Cmd+Tab` artifacts to another app
- The cursor isn't in a weird position (mid-button, twitching)

**Re-shoot if:**
- Cold-start latency made the PDF extract take 20+ seconds (warm Railway again)
- The agent's reply doesn't mention what we expected (bulking in scene 5, $250 cap in scene 7) — usually means setup step 3 or scene 4 didn't take
- A button click missed and the user clicked twice
- The dashboard came up with synthetic seed data — means the wipe (setup step 1) didn't run
