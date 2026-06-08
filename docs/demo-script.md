# Demo Script — 90 seconds

> Write this **before** Week 3, not during. The video is the deliverable that wins the hackathon — the code only matters insofar as it can produce these 90 seconds.

## Hard rules

1. **90 seconds max.** If it runs over, cut a beat — don't speed up the narration.
2. **No app tour.** Don't explain features. Show the agent doing something nobody else can.
3. **One user, one story arc.** "Sarah" or "Alex" — pick a name on day one.
4. **Show, then explain.** Every voice-over line is justified by something happening on screen.
5. **Only show what's actually on screen.** No mock UI in the video. If a beat depends on a panel/widget/view that doesn't exist in the live app, cut the beat or pick a different beat — don't fake it.

## Beat sheet

| Time     | On screen                                                              | Voice-over                                                                                  |
| -------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 0:00–0:08 | MoneyMind logo, then cut to a phone notification appearing             | "Tuesday, 7pm. Alex didn't open the app. The app opened itself."                            |
| 0:08–0:22 | iMessage-style chat: agent's food-spike message lands, types out       | "It noticed her food spend jumped — and remembered the same pattern from February."          |
| 0:22–0:32 | Alex replies "Busy week at work, no time to meal prep."                | "She tells it what's going on."                                                              |
| 0:32–0:45 | Agent proposes a $200/mo food cap (V6 intervention card), Alex taps Accept; card collapses into a confirmation that the budget is now live in Atlas | "It proposes a fix anchored in her actual life — and the cap is live the moment she accepts." |
| 0:45–1:00 | **Cut to** Alex dragging her May bank-statement PDF onto the chat. The V4 import-progress card mounts and steps through Received → Dedupe → Reading the PDF (Gemini 2.5 Flash) → Found N transactions → Categorizing → Saving to MongoDB Atlas, then morphs into the StatementCard summary | "She drops in her May statement. Gemini reads every line, categorizes it, writes it to Atlas — in seconds, in front of you." |
| 1:00–1:10 | Time-lapse: dashboard at Day 1 (sparse) → Day 30 (some patterns) → Month 6 (memories, goals, budgets populated) | "Six months in, it's not the same product. It's a model of Alex."                  |
| 1:10–1:22 | Architecture slide-10 SVG renders, three layers light up               | "Built on Gemini and Vertex AI. One MongoDB Atlas cluster does all four jobs — ledger, vector recall, agent memory, and MCP read tools." |
| 1:22–1:30 | MoneyMind logo + tagline: "An AI co-pilot that remembers who you are." | "MoneyMind. The agent every bank will build in eighteen months — we shipped it in two weeks." |

### Why the V4 PDF drop replaced the memory-write panel

The original script promised a 0:45–0:55 "memory document being written in real time" beat in a right rail on the chat page. **That panel does not exist in the live app** — the chat is a single column with a paperclip upload button, intervention cards, and statement cards. Recording the original beat would mean either (a) faking a UI we never shipped, or (b) cutting to a Mongo Compass screen mid-demo, which breaks the show-don't-explain rule.

The PDF drop is a stronger beat anyway:
- **It's already built and animated** — `components/chat/import-progress.tsx` runs a 6-step SSE-driven timeline that morphs in real time.
- **It's multimodal and visibly multi-step** — judges see Gemini 2.5 Flash reading a real PDF, dedupe via content-addressed hash, categorization, and the Atlas write. That's the whole stack on screen in one card.
- **It earns the "MongoDB track" claim visually** — the final step literally says "Saving to MongoDB Atlas," then the card morphs into a StatementCard showing the inserted rows.

The intervention beat (0:32–0:45) also got stronger after V6: tapping **Accept** on a cap intervention now writes a real budget document to Atlas via `set_budget`, so the on-screen "card collapses into a live budget" beat is true, not aspirational.

## Capture checklist (do these before recording the voice-over)

- [ ] Synthetic data feels real on camera (no obvious test rows like `Test Merchant 1`).
- [ ] Agent voice has been tuned over 10 sample conversations.
- [ ] Stage a real PDF for the V4 drop — clean issuer header, 8–15 line items, dated within the demo window. Test the upload twice on a warm container so the 6 steps land in <8 seconds on camera.
- [ ] The import-progress card steps are legible at 720p (esp. the "Saving to MongoDB Atlas" line — that's the track-eligibility moment).
- [ ] After Accept, confirm the new budget shows up on the dashboard before cutting — proves the V6 cap-accept actually materialized in Atlas.
- [ ] Dashboard has at least 4 visible widgets at Month 6 — sparse-vs-dense contrast is the visual hook.
- [ ] App is in dark mode for the full recording (matches the pitch deck).

## Tools

- **Screen capture:** ScreenStudio or CleanShot X (zoom-on-click matters).
- **VO:** record dry, no music underneath. Add subtle ambient bed in post.
- **Edit:** Final Cut or DaVinci. Keep cuts tight — no fades over 200ms.

## What to cut if it runs long

In order of expendability:
1. The architecture beat (1:10–1:22) — judges will see the deck separately.
2. The time-lapse (1:00–1:10) — shrink to 3 seconds with a counter (`Day 1 → Month 6`).
3. The opening notification (0:00–0:08) — start cold on the chat message instead.

**Never cut:** the chat exchange + intervention accept (0:08–0:45) or the V4 PDF drop (0:45–1:00). Those are the product.
