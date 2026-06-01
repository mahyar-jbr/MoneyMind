# Decision Log

> One entry per non-trivial choice. Three sentences each. New entries at the top.

## 2026-05-31 — Memory writers populate `embedding` themselves; Atlas auto-embed is NOT on

**Context:** #3 said "vector index READY" and the architecture doc described Voyage auto-embed. #13 verified live: the cluster has the *vector index* set up correctly (1024-dim cosine, filters on user_id + type), but the *auto-embed pipeline* on a source field was never configured. A doc inserted without an `embedding` field stays unindexed and unfindable.

**Decision:** Writers (#14, the cron in #21, the #13 demo script) compute and persist embeddings themselves via `agent.embeddings.voyage.embed_document()` before the insert. This is the working state today and ships the feature without touching cluster config. `#3a` is the optional follow-up to flip auto-embed on in Atlas; if we ever do, writers can drop the explicit embed call.

**Trade-off:** Every write costs one Voyage call (~free-tier limited). Adds ~200ms latency to memory writes. Acceptable: writes are rare relative to reads, and the alternative (auto-embed) requires deeper cluster config plus a working-pattern audit. `#13b` separately covers the rate-limit hardening.

**Revisit:** If auto-embed gets configured (`#3a`), drop the explicit `embed_document()` from `#14`'s write path and the demo scripts. Vector index itself does not change.

## 2026-05-31 — Anomaly tool uses Python-side 7-day buckets, not Mongo `weekly_spend_by_category`

**Context:** #12 needs to compute a per-week baseline of category spend. The natural choice is to call the existing `weekly_spend_by_category` aggregation (Mongo `$dateTrunc` with `startOfWeek: monday`). But `mongomock-motor` doesn't implement `$dateTrunc`, so calling the aggregation would force every Sprint 2 tool test against real Atlas — ~30s per run × 9 remaining tools × every CI run, vs. <1s hermetic.

**Decision:** `#12` does Python-side bucketing into exactly `baseline_weeks` consecutive 7-day buckets anchored at `baseline_start`. `agent/aggregations/weekly.py` is still landed as a faithful mirror of the backend's function — reserved for tools where the OUTPUT must be calendar weeks (e.g. `#20 summarize_week`). For statistical buckets feeding an anomaly z-score, anchored 7-day windows are actually *more* correct (the divisor is exactly `baseline_weeks`, no calendar drift).

**Trade-off:** The two paths produce slightly different numbers for the same date range — `#12`'s baseline ≠ `/agg/weekly` for the same span. Acceptable: their consumers are different (the agent's anomaly check vs. the API's weekly breakdown). Documented in `#12`'s implementation note so a future reader doesn't try to "fix" the divergence.

**Revisit:** If `mongomock-motor` ever ships `$dateTrunc` support, or if we replace it with a real test-Atlas, the mirror module becomes the single call site and the Python bucketing can go away. Not on the critical path.

## 2026-05-27 — Agent tools take an injected `collection=None` kwarg; wired to the graph in batches

**Context:** Shipping #11 forced two choices that will cascade across every Sprint 2 tool (#12–#20). First, how do tools get their Mongo handle — globals via `get_database()` or dependency-injected? Second, when do we wire each tool into the LangGraph graph — per-ticket or batched?

**Decision:** Tools take an optional `collection=None` kwarg; when None, they fall back to `agent.db.client.get_database().<coll>`. Tests inject a `mongomock-motor` fake — proven in #11: 12 tests run in <1s vs. ~30s/run against Atlas. Graph wiring is deferred to a single batched migration ticket (#11a) after ~4 tools exist, switching to `create_react_agent` with the tool list as input. Per-tool wiring would mean rewriting the graph 10 times.

**Trade-off:** Tools land "callable but unwired" between #11 and #11a — the chat flow can't use them yet. Acceptable: it's ~2–3 tickets of latency, and the alternative (per-ticket wiring) churns the graph shape and the prompt every time. The kwarg also adds a tiny API-surface wart (`collection=None`), which is fine.

**Revisit:** Never for the kwarg — it's a stable testing pattern. The batching cadence can flex: if a tool genuinely *requires* graph integration to verify (e.g. one that only makes sense inside a tool-call loop), pull #11a forward.

## 2026-05-27 — Streaming granularity: accept Gemini's coarse chunks, no resmoothing

**Context:** Skeleton (#10) streams correctly leg-to-leg, but `gemini-2.5-flash` via langchain emits only 2–3 coarse blocks (~3.5s to first block) for a short reply — so it lands in 1–2 bursts, not a smooth typewriter. The AC ("first token before generation finishes") is technically met. Question: add a client-side token-resmoothing drip now, or leave it.

**Decision:** Leave it. No resmoothing ticket. This is demo polish, not skeleton scope — it belongs to Sprint 3 (#26 frontend polish), decided when @aidin records against tuned conditions and we can see whether the chunking actually reads badly on camera.

**Trade-off:** The dev chat won't *look* like live streaming until/unless we add the drip. Acceptable — it's a ~20-min change in `chat-stream.ts` if Sprint 3 needs it, and doing it now risks reworking a wire that #24 (MCP) may still touch. Logged as a Sprint-3 watch item, not a backlog ticket.

**Revisit:** Sprint 3, at demo-video recording. If Gemini's bursts look janky at 720p, add the client-side drip then.

## 2026-05-27 — "This week" = latest week with data, not calendar week

**Context:** The agent's weekly-spend grounding needs to resolve "this week." The synthetic CSV ends 2026-05-23; the real calendar week (today 2026-05-27) is empty, so a strict calendar-week reading would cite nothing and the demo reply would be hollow.

**Decision:** "This week" resolves to the latest week in the data that has transactions. The agent cites the most recent populated week (2026-05-18: food.delivery $211.21, total $436.33).

**Trade-off:** Not literal calendar semantics — if a user had a genuinely empty current week, the agent would talk about an older one without saying so. Fine for a single-user demo on fixed synthetic data; the alternative (re-dating the CSV every day to keep "this week" populated) is fragile demo-maintenance we don't want.

**Revisit:** If the demo ever runs on live/rolling data. Then either re-date synthetic data on a schedule or make the agent state which week it's referring to.

## 2026-05-27 — Chat wire format: plain-text chunked, not SSE

**Context:** PR #7 review caught that the chat shell streams `text/plain` word chunks while `docs/architecture.md` commits us to server-sent events. Three legs have to agree on one format — `chat-stream.ts`, the `/api/chat` proxy (#8a), and the agent's `/chat` output — and #8a + #10 both block on the answer.

**Decision:** Plain-text chunked streaming. SSE's value (named events, auto-reconnect, event IDs) is unused for a single-turn, one-response stream that closes when the agent finishes; the shell already does plain text, so this is also the zero-rework path.

**Trade-off:** Gives up SSE's reconnect semantics — if the connection drops mid-stream the user re-sends rather than auto-resuming. Acceptable: it never appears in the 90s demo and costs a day to do "right." `architecture.md` updated to match. Tracked as #8b.

**Revisit:** Post-freeze, only if we ever ship multi-turn server-push (e.g. the cron nudge arriving while the chat is open). That's a different channel anyway.

## 2026-05-21 — Agent boot: use `PYTHONPATH=..`, not editable install

**Context:** `uv init --app` doesn't install the project as a package, so `uvicorn agent.serve:app` fails with `ModuleNotFoundError`. Three options on the table: (a) document `PYTHONPATH=..` in the README; (b) add `[build-system]` + hatchling to install editably; (c) drop the `agent.` namespace and run from inside `agent/`.

**Decision:** Option (a). Working state shipped. Option (b) was attempted and burned 20 min — `uv sync` reported the editable install succeeded, but `pytest` then hung indefinitely during collection (suspected sys.path conflict between the editable `.pth` and `pythonpath=["."]` in pytest config).

**Trade-off:** `PYTHONPATH=..` is ugly in three places (README, docs/setup.md, `serve.py` docstring) but works end-to-end and doesn't fight the test harness. Option (c) would have broken the `agent.tools.foo` import pattern Sprint 2 needs.

**Revisit:** Post-freeze as ticket #9b. Worth fixing once we have time to debug the pytest hang, but not on the critical path.

## 2026-05-21 — CSV ingest: overwrite on duplicate `source`

**Context:** Reviewing PR #2 (Kasra's CSV ingest), the reviewer asked what should happen when a user re-uploads the same CSV file. Options were overwrite (simple, risk of losing data on bad re-upload), append (safe, risk of doubled rows skewing the agent), or idempotent upsert (correct but more code).

**Decision:** Overwrite. Same `source` key = wipe old rows for that source, insert new. Combined with the blocking fix on PR #2 (insert-then-delete instead of delete-then-insert), this stays safe even if the second upload fails.

**Trade-off:** Gives up the safety of append/idempotent for hackathon simplicity. Acceptable because the only data source until demo day is `data/synthetic.csv` — we control both the input and when re-uploads happen.

**Revisit:** Post-hackathon, if anyone tries to use this beyond the demo. Idempotent upsert (source + row hash) is the right long-term answer.

---

## 2026-05-21 — Clerk auth ships in slot (#7), not fast-tracked

**Context:** Reviewer flagged that PR #2's `user_id` form field is a security gap once Clerk lands. Question was whether to fast-track #7 ahead of #4–6.

**Decision:** Keep #7 in its original Sprint 1 slot. Sprint 1's goal is the walking skeleton; until #7 lands, the ingest endpoint accepts `user_id` as a required form field (per PR #2 review).

**Trade-off:** A few days of unauthenticated upload risk on a localhost-only dev service. Zero real-world impact.

**Revisit:** Once #7 merges, follow-up ticket #4a swaps the form field for Clerk JWT resolution.
