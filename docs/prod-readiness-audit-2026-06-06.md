# MoneyMind — Production-Readiness Audit

**Date:** 2026-06-06 · **Auditor:** Claude (Opus 4.8, ultra effort) · **Method:** 5 parallel surface-auditors + 13 adversarial verifiers (18 agents), plus hands-on live-service + test-suite verification.

**Verdict:** The product is **80% production-ready**. The backend, agent, data layer, and deploy are genuinely solid and live. There is **one demo-critical gap** (the headline intervention feature is faked in the UI) and a cluster of doc/config inaccuracies that hurt a judged submission. Fix the blocker + the data-contract bug and you're demo-ready; fix the doc cluster and you're submission-clean.

---

## ✅ What's working (verified end-to-end)

- **Live services up:** Frontend (Vercel) `HTTP 200`; Backend (Railway) `/health → {ok:true, mongo:true}`, Atlas connected.
- **All 10 backend routes** exposed and Clerk-authed (`/agg/weekly`, `/transactions`, `/inbox`, `/chat`, `/ingest/csv`, `/interventions/pending`, `/interventions/{id}/respond`, `/agent/run-weekly-summary`, `/agent/run-reminders`, `/health`). No auth bypass found — every route shares the `current_user` dependency.
- **All 11 agent tools registered** in the LangGraph ReAct loop with graceful MCP fallback (spawn failure → `[]`, agent still boots).
- **Chat path is real end-to-end:** frontend `/api/chat` → Clerk JWT → backend `/chat` → agent loopback (`_require_loopback_client`, not a spoofable header) → Vertex Gemini → token stream piped back chunk-by-chunk. Wire format consistent on all three hops.
- **Dashboard path is real end-to-end:** StatCards / SpendChart / CategoryBreakdown / TransactionsList / Inbox all read live Atlas data through Clerk-gated proxies. Loading / empty / error states all handled.
- **Tests green:** agent **232 passed**, backend **35 passed** (267 total). Frontend `tsc --noEmit` exits 0.
- **Auth gating correct:** `middleware.ts` protects `/dashboard`, `/chat`, and all four implemented API proxies; each proxy independently re-checks `userId`+token.

---

## 🚨 BLOCKER — fix before recording the demo video (#27)

### B1. The intervention card is 100% mock theater — the headline feature is fake in the UI
**`frontend/lib/interventions.ts:45-69`** · category: mock-stub · **BACKLOG #22a, still open**

All 5 independent auditors flagged this; all verifiers confirmed it.

- `fetchPendingInterventions()` returns **one hardcoded "Sunday meal prep" reminder** via a module-level `served` latch, then `[]` forever after.
- `respondToIntervention()` is a **literal no-op** — `void [...]; await sleep(200)`. It doesn't even pretend to hit the network. Accept/Decline/Modify persists **nothing**; the agent's `respond_to_intervention` tool never fires; no memory is written.
- The chat page shows this canned card after the **first** reply regardless of what the agent actually did. The agent's real `propose_intervention` Atlas writes are **invisible**.

**Why it's a blocker:** This is slide 8 of your pitch — the proactive/memory learning loop, your core differentiator. On camera it's fake. The backend is *fully built and live* (`/interventions/pending` + `/interventions/{id}/respond` exist and are tested). This is a pure **frontend wiring gap**, ~15–25 lines.

**Fix:**
1. Add `frontend/app/api/interventions/pending/route.ts` (GET) and `frontend/app/api/interventions/[id]/respond/route.ts` (POST), mirroring `app/api/transactions/route.ts` (Clerk `auth()` → `getToken()` → `backendUrl()` → `Authorization: Bearer`).
2. Add both paths to `middleware.ts` `isProtectedRoute`.
3. Replace the two mock bodies in `lib/interventions.ts` with real `fetch()` calls — **but watch B2 and B3 below, or it'll silently break.**

---

## 🔴 HIGH — these bite the moment you wire the blocker

### B2. Data-contract mismatch: backend returns `id`, frontend reads `intervention_id`
**`frontend/lib/interventions.ts:6` vs `backend/app/api/interventions.py:36,84`** · data-contract

The mock papers over three mismatches that a naïve fetch will hit:
- Backend serializes `_id → id`; frontend type expects `intervention_id`. Result: `key={undefined}` (React key collisions) and `POST /interventions/undefined/respond` → backend 404/400.
- Backend wraps the list in `{interventions: [...]}`; frontend expects a bare array (must unwrap like `getInbox`/`getTransactions` do).
- Respond body keys differ: frontend sends `{response, modifiedParams}`; backend `InterventionResponseRequest` expects **`{user_response, modified_params}`**.

**Fix:** In the new proxy/lib adapter, map `id → intervention_id`, unwrap `.interventions`, and remap the respond payload to `{user_response, modified_params}`. Add one integration smoke test against the real endpoint.

### B3. Chat re-appends the same pending card every turn (no dedup)
**`frontend/app/chat/page.tsx:90-101`** · bug

After every reply the page appends *all* pending interventions with no dedup. Against the real backend, a still-pending nudge re-appears as a fresh card on every subsequent turn → thread fills with duplicates. (Latent today only because the mock returns `[]` after the first call.)

**Fix:** Dedup before appending —
```ts
const existing = new Set(
  messages.filter((m) => "kind" in m).map((m) => m.intervention.intervention_id),
);
const fresh = pending.filter((it) => !existing.has(it.intervention_id));
```
Combine with B1 so accepted/declined docs leave the pending set server-side.

---

## 🟠 MEDIUM — submission credibility / cold-start robustness

| # | Issue | File | Fix |
|---|-------|------|-----|
| M1 | **Docs claim "Voyage auto-embed"** but code embeds manually on insert (your own `decisions.md` says auto-embed isn't configured). | `README.md:23`, `architecture.md:32`, `data-model.md:98` | Say "Voyage AI embeddings (written explicitly on insert)". |
| M2 | **`setup.md` / `agent/README.md` tell you to use `GEMINI_API_KEY` + google-genai + "Gemini 3"** — but the code uses **Vertex AI (`ChatVertexAI`) + service-account ADC + `gemini-2.5-flash`**. Following setup.md from scratch → agent crashes at `_build_llm()`. `GEMINI_API_KEY` is dead config. | `docs/setup.md:28`, `agent/README.md:4` | Rewrite setup to provision the Vertex SA + `GOOGLE_CLOUD_PROJECT`/`_LOCATION`/`GOOGLE_APPLICATION_CREDENTIALS`; drop `GEMINI_API_KEY`; correct "Gemini 3" → "Gemini 2.5 Flash (Vertex AI)". |
| M3 | **`GOOGLE_APPLICATION_CREDENTIALS_JSON_B64` is the real prod credential mechanism but is undocumented in `.env.example`.** A fresh Railway redeploy boots, `/health` green, then the **first `/chat` crashes** on missing ADC. | `.env.example:12-17`, `deploy/entrypoint.sh:17-26` | Add a labeled production section documenting `*_JSON_B64` as the deploy credential. |
| M4 | **MCP server fetched at runtime via `npx -y mongodb-mcp-server@latest`** — not baked into the image. First chat turn after cold deploy pays an npm-registry round-trip on top of Vertex warmup; if npm is slow/unreachable, your MongoDB-track headline feature silently falls back to `[]` with only a log line. | `agent/mcp_integration/client.py:53-58`, `Dockerfile` | `RUN npm install -g mongodb-mcp-server@<pinned>` in the Dockerfile; spawn the installed binary; pin the version (drop `@latest`); pre-warm in lifespan. |
| M5 | **Production landing page embeds a third-party Spline iframe** the comment marks "prototype, preview only, not committed" (it *is* committed to `main`). If the external scene is deleted/rate-limited during judging, the hero renders broken; the iframe is also scaled to clip Spline's attribution badge (possible ToS issue). | `frontend/app/page.tsx:24-32` | Self-host a poster/video or committed Spline export, or gate behind a load/error fallback to the CSS ambient glow. Confirm the scene stays live through judging. |

---

## 🟡 LOW / housekeeping

- **Delete duplicate conflict-artifact files** (macOS "Keep Both" copies, byte-identical, never imported): `backend/app/api/interventions 2.py`, `backend/tests/test_interventions_api 2.py`. The test copy runs 6 tests twice; the source copy is a merge-hazard if anyone globs `api/*.py`.
- **Agent graph rebuilt on every chat turn** (`agent/graphs/main.py:382-388`) — re-creates the Vertex client + re-wraps 11 tools + re-compiles per message. Cache it at module level; only per-user context fetch needs to run per request. Avoidable latency/cost.
- **Dead/misleading MCP env vars** (`MCP_ENABLED`, `MCP_SERVER_URL`) — never read; the real var is `MONGODB_MCP_TRANSPORT` and the server is a stdio subprocess, not HTTP. Either honor `MCP_ENABLED` (return `[]` when false) or remove the vars.
- **`recall_memory` uses hard subscripts** (`doc["tag"]`...) on vector-search results — a hand-inserted malformed memory doc would `KeyError` and silently hang the chat turn. Use `.get()` / `$ifNull`. (Won't fire on the normal demo path.)
- **`/agent/run-reminders` lacks the try/except** that `run-weekly-summary` has — raw 500 instead of clean 502 if Mongo errors during pre-take seeding.
- **Backend→agent chat proxy uses `timeout=None`** (`chat.py:33`) — bounded in practice by the agent's 240s warmup cap, but a mid-stream Vertex hang would hang the user's chat with no client-visible timeout. Set an explicit `httpx.Timeout`.
- **Doc tool-count drift:** `architecture.md` says 10, README says 11 (code = 11 native). Backlog says 242 agent tests; actual = 232. `create_react_agent` deprecation warning (no runtime impact, lockfile frozen).
- **No Clerk redirect URLs configured** — dedicated `/sign-in`,`/sign-up` + post-auth redirect rely on Clerk defaults; flow can bounce to the hosted portal instead of staying in-app. Set `NEXT_PUBLIC_CLERK_SIGN_IN_URL`/`SIGN_UP_URL`/`*_FALLBACK_REDIRECT_URL`.

---

## ⚠️ Open questions for you (design intent, not bugs)

1. **Chat is single-turn from the frontend.** `/api/chat` forwards only the *last* user message (`route.ts:33,47`) — no conversation history reaches the agent. The slide-8 two-turn "Yeah, busy week…" follow-up won't have prior-turn chat context unless the agent reconstructs it from Atlas memory/thread state. **Intended?**
2. **No scheduler for the "proactive" cron.** Weekly summary + reminders only run via authenticated manual POST (cron deferred post-freeze per #21). Fine if you fire it off-camera, but a judge asking "how does the weekly nudge fire automatically?" finds no scheduler. Decide: add APScheduler/Railway cron, or soften the architecture doc.
3. **CSV ingest is operator-only** — no UI/proxy. A judge can't upload their own CSV through the product. Intended (seed-via-script), but worth a conscious call.

---

## Recommended order

1. **B1 + B2 + B3 together** (interventions: proxies + real fetch + id-mapping + dedup) — one focused PR. Unblocks #27.
2. **M2 + M1 + M3** (doc accuracy: Vertex setup, no auto-embed, document the B64 cred) — submission credibility.
3. **M4** (bake + pin the MCP server) — protects the MongoDB-track headline on demo day.
4. **M5** (de-risk the Spline hero).
5. Housekeeping: delete the ` 2.py` dupes, cache the graph, fix the env-var docs.

Everything above is verified against the actual code with verbatim citations (12/13 confirmed, 1 partial, **0 false positives**).
