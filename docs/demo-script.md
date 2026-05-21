# Demo Script — 90 seconds

> Write this **before** Week 3, not during. The video is the deliverable that wins the hackathon — the code only matters insofar as it can produce these 90 seconds.

## Hard rules

1. **90 seconds max.** If it runs over, cut a beat — don't speed up the narration.
2. **No app tour.** Don't explain features. Show the agent doing something nobody else can.
3. **One user, one story arc.** "Sarah" or "Alex" — pick a name on day one.
4. **Show, then explain.** Every voice-over line is justified by something happening on screen.

## Beat sheet

| Time     | On screen                                                              | Voice-over                                                                                  |
| -------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 0:00–0:08 | MoneyMind logo, then cut to a phone notification appearing             | "Tuesday, 7pm. Alex didn't open the app. The app opened itself."                            |
| 0:08–0:22 | iMessage-style chat: agent's food-spike message lands, types out       | "It noticed her food spend jumped — and remembered the same pattern from February."          |
| 0:22–0:32 | Alex replies "Busy week at work, no time to meal prep."                | "She tells it what's going on."                                                              |
| 0:32–0:45 | Agent replies, proposes the Sunday reminder, Alex accepts              | "It proposes a fix anchored in her actual life — not a generic budgeting tip."                |
| 0:45–0:55 | **Cut to** the memory document being written in real time (slide-8 right panel) | "And it remembers. Next time, it already knows the cause."                          |
| 0:55–1:08 | Time-lapse: dashboard at Day 1 (sparse) → Day 30 (some patterns) → Month 6 (47 facts) | "Six months in, it's not the same product. It's a model of Alex."                  |
| 1:08–1:20 | Architecture slide-10 SVG renders, three layers light up               | "Built on Gemini and Google Cloud Agent Builder. One MongoDB Atlas cluster does all four jobs." |
| 1:20–1:30 | MoneyMind logo + tagline: "An AI co-pilot that remembers who you are." | "MoneyMind. The agent every bank will build in eighteen months — we shipped it in two weeks." |

## Capture checklist (do these before recording the voice-over)

- [ ] Synthetic data feels real on camera (no obvious test rows like `Test Merchant 1`).
- [ ] Agent voice has been tuned over 10 sample conversations.
- [ ] The "memory writes" panel animates clearly enough to read at 720p.
- [ ] Dashboard has at least 4 visible widgets at Month 6 — sparse-vs-dense contrast is the visual hook.
- [ ] App is in dark mode for the full recording (matches the pitch deck).

## Tools

- **Screen capture:** ScreenStudio or CleanShot X (zoom-on-click matters).
- **VO:** record dry, no music underneath. Add subtle ambient bed in post.
- **Edit:** Final Cut or DaVinci. Keep cuts tight — no fades over 200ms.

## What to cut if it runs long

In order of expendability:
1. The architecture beat (1:08–1:20) — judges will see the deck separately.
2. The time-lapse (0:55–1:08) — shrink to 3 seconds with a counter (`Day 1 → Month 6`).
3. The opening notification (0:00–0:08) — start cold on the chat message instead.

**Never cut:** the chat exchange (0:08–0:55) or the memory write panel reveal. Those are the product.
