# Decision Log

> One entry per non-trivial choice. Three sentences each. New entries at the top.

## 2026-06-01 — CSV re-uploads append when content changes; exact duplicates are cleaned by dedupe

**Context:** The 2026-05-21 CSV ingest decision said duplicate `source` uploads overwrite prior rows. That worked while `source` was a date-only import key, but it caused demo data collisions and doubled rows in Atlas when multiple files shared the same import date. PR `#11b` changes the source key to include upload filename plus a content hash, so a corrected re-upload with different bytes is treated as a new import rather than overwriting the previous one.

**Decision:** CSV import source keys are content-addressed enough for demo scale: `csv_import_<date>_<filename_slug>_<sha256-prefix>`. Re-uploading the exact same file still overwrites same-source rows safely, while re-uploading corrected content appends as a distinct source. Existing doubled Atlas rows are handled by the one-shot exact-row dedupe script, which keeps the oldest `_id` in each duplicate group and deletes later copies only when `--apply` is passed.

**Trade-off:** Historical corrected imports remain visible instead of being replaced in place. Acceptable — it preserves auditability and avoids accidental data loss on demo day; if the product later needs explicit import replacement, that should be a separate import-management feature with user-visible source metadata.

**Revisit:** If real users upload corrected bank exports often enough that old imports clutter analytics. At that point add a first-class `imports` collection and replacement flow instead of overloading `transactions.source`.

## 2026-06-01 — Tools don't call other tools; agent layer is the composition point

**Context:** `#20 summarize_week` is the first Sprint 2 tool that *could* have called other tools — it naturally wants spend totals (mirror of `#12`'s anomaly substrate), goal pace (`#16`), and could even pre-flag anomalies. The temptation is to import `check_goal_pace` and reuse its 8-verdict ladder. Doing so would create a hidden call-depth nesting: LangGraph's tool-call routing sees ONE tool call from the LLM, but multiple Mongo reads happen, each with its own user_id injection path and its own error surface. That asymmetry breaks every reasoning the LangGraph debugger and the prompt's tool-use philosophy depend on.

**Decision:** Tools stay flat. Tool A does NOT call tool B. If a chat turn wants summary + recall + anomaly, the AGENT composes them in sequence — the LangGraph ReAct loop is the composition surface, designed for exactly this. When a tool needs functionality another tool *also* needs (e.g. `#20`'s simpler 4-state goal note vs. `#16`'s 8-verdict ladder), inline the math rather than nest the call. Acceptable divergence: `#16` is for "tell me about THIS goal" (verdict-rich), `#20` is for "give me a snapshot" (compressed). Shared low-level helpers (e.g. `agent/aggregations/weekly.py`'s `weekly_spend_by_category`) are NOT tools — they're plain functions and can be imported freely.

**Trade-off:** Some code duplication across tools (e.g. `_pretty(category)` shows up in `#12`, `#20`, and likely future tools). Acceptable — duplication is local and visible; nesting hides execution paths from the graph and the reviewer. The "extract on second use" rule from `#14a` still applies to plain helpers (e.g. `_pretty` is a candidate for `agent/tools/_format.py` if a third tool needs it), just not to tool-to-tool calls.

**Revisit:** If we ever build a "compound" tool that the LLM should see as ONE action (e.g. "give me the full briefing"), that's a real design moment — likely a new tool whose body inlines several reads, not a tool-of-tools.

## 2026-06-01 — New `reminders` collection (not in original data-model); UTC-instant fields are a deliberate exception to convention 5

**Context:** `#19 schedule_reminder` is for one-off pings — user-requested or agent-self-scheduled, no approval flow, no outcome. The original `data-model.md` schema list (transactions / goals / memories / interventions / outcomes / user_context) didn't include this surface. Two design options were rejected: reuse `interventions` with `type="reminder"` (bundles two unlike lifecycles — interventions have Accept/Decline + outcome measurement; reminders just fire), and embed in `user_context` (user_context is for state, not scheduled events). Separately, `fires_at` represents an instant in time the cron compares to `now()` every tick — naive datetimes plus a cron across timezones is exactly the production-bug shape we want to avoid.

**Decision:** Two locks. (1) New `reminders` collection, schema documented in `data-model.md § reminders`. Schema: `{user_id, fires_at, text, source ("user"|"agent"), related_intervention_id (ObjectId|null), status ("pending"|"fired"|"cancelled"), created_at, fired_at}`. Canonical "pending due by T" predicate is pinned in the same section so the `#21` cron and any future reader can't drift. (2) `fires_at` and `fired_at` persist as **UTC instants**, NOT naive midnight datetimes — a deliberate exception to architecture.md convention 5. Convention 5 is amended to distinguish calendar-day fields (naive midnight, the default) from instant-in-time fields (UTC-aware, this new path). The interventions-vs-reminders boundary is also pinned as a table in the data-model section.

**Trade-off:** Adds one collection + one convention sub-rule. Acceptable — bundling reminders into interventions would force every intervention reader (cron, dashboard, future analytics) to type-check, and naive datetimes for instant-in-time fields invite bugs we'd then chase across timezones. The convention 5 amendment is a precise carve-out, not a loosening: every existing field stays naive-midnight; only `reminders.fires_at` and `fired_at` are UTC-instant. pymongo's default tz-stripping behavior means comparisons still work (`{$lte: datetime.now(UTC)}` vs. naive read), documented in the data-model section so the cron author isn't surprised.

**Revisit:** If a future tool needs instant-in-time semantics for a NON-reminders field, the convention 5 sub-rule already covers it. If we ever want recurring reminders (vs. one-off), that's a redesign moment — recurring is what interventions cover today, and `schedule_reminder` deliberately writes single-fire docs.

## 2026-06-01 — outcomes shape locked by #18; delta_pct is server-computed, snippet precision corrected to 2dp

**Context:** `#18` is the first writer to `atlas.outcomes` — same schema lock-in window as `#14` (memories), `#15` (user_context), `#16` (goals' first read+write), `#17` (interventions). The data-model.md snippet for outcomes showed `delta_pct: -34.2` (1dp), but the persistence contract needed to be 2dp — both for the agent's downstream reasoning ("interventions of type X have worked Y.YY% of the time") and to match `#18`'s tested worked example (`-34.17`).

**Decision:** Three locks. (1) Outcomes shape conforms to `docs/data-model.md § outcomes` exactly — now amended with field-level commentary (FK type for `intervention_id`, server-stamping for `measured_at`, the `abs(before)` rule, the `before=0` deterministic return, agent vs. user judgment). (2) `delta_pct` is SERVER-COMPUTED by `#18` from `(after - before) / abs(before) * 100`, rounded to 2dp; the input model deliberately has no `delta_pct` field so the agent cannot pass it. Same separation as `#14`'s server-stamped `created_at`. (3) `log_outcome` does NOT mutate the corresponding intervention doc — outcomes and interventions are joined by `intervention_id`, never by cross-mutation. The 1:1 logical relationship is unenforced by the schema (no unique index); the agent's prompt prevents double-logging.

**Trade-off:** Tightens the data-model snippet's precision example from `-34.2` to `-34.17`. Acceptable — anyone reading the snippet to predict tool behavior gets the right answer. Adds field-level commentary that's strictly explanatory, not contract-bending; the persisted shape is unchanged. The "no cross-mutation" rule prevents a tempting shortcut (flipping a `has_outcome` boolean on the intervention) but keeps the two surfaces independently evolvable.

**Revisit:** If the agent's prompt ever drifts and starts double-logging outcomes for the same intervention. That's the signal to add a unique compound index on `(user_id, intervention_id)` to enforce schema-side, rather than prompt-side.

## 2026-06-01 — interventions shape locked by #17 + new `status` field added; respond_to_intervention contract pre-spec'd

**Context:** `#17` is the first writer to `atlas.interventions` — same schema lock-in window as `#14` (memories), `#15` (user_context), and `#16` (goals' first read+write). `data-model.md § interventions` showed only the *answered* form of the doc (`user_response: "accepted"`, `responded_at: <date>`), so it under-specified the pending state that `#17` actually produces. Readers will also frequently query "which interventions still need a response?" and a `{user_response: null}` filter is awkward for the LLM and unindexed by default.

**Decision:** Three locks. (1) The persisted shape conforms to `data-model.md § interventions` exactly — now amended to call out the pending form. (2) At propose time, `user_response` and `responded_at` are explicitly null; the data-model snippet is updated to make this part of the contract, not an example artifact. (3) NEW field `status: "pending" | "responded" | "ignored"` added on top of the data-model snippet — written as `"pending"` by `#17`, flipped by the future `respond_to_intervention` tool (`#17a`). Indexable, LLM-readable, and decouples reader queries from the user_response semantic. The `#17a` contract is pre-spec'd in the `#17` dev report and the `#17a` backlog row: lookup by `intervention_id + user_id`; set the three response fields; flip status; do NOT touch related_memory's use_count (that's `#13a`).

**Trade-off:** Adds one field beyond the original data-model snippet. Acceptable — it's cheap to index, removes the "is null" awkwardness across every reader, and the alternative (every reader deriving status from `user_response == null`) leaks the same logic into N call sites. The reverse migration is trivial if it ever bothers us: `$unset` the field.

**Revisit:** When `respond_to_intervention` (#17a) ships and Aidin's #22 UI is wired against it. If the trio (propose → respond → status) doesn't compose cleanly under real chat flow, that's a redesign moment.

## 2026-06-01 — Async DB calls fetch BEFORE the graph runs, not inside its prompt builder

**Context:** `#11a` originally specified that the graph's prompt builder would fetch active `user_context` per turn. In practice, `create_react_agent`'s prompt builder is invoked from inside an already-running asyncio loop, and motor's cursors bind to the loop they were created on. The natural sync-from-async path (`asyncio.run`) creates a new loop, and motor blows up with "Future attached to a different loop." Workarounds like `asyncio.get_event_loop` are flaky across Python versions.

**Decision:** Any DB read needed for the system message is pre-fetched in the public entry points (`run_chat` / `arun_chat` / `stream_chat`) BEFORE the graph runs, then passed via state as a pre-formatted string. The prompt builder is pure-sync: it concatenates the SYSTEM_PROMPT with whatever state already contains. `agent/graphs/main.py`'s `_build_initial_state` does the fetch; `_prompt_builder` only reads.

**Trade-off:** Loses the "prompt builder fetches anything it wants per turn" cleanliness. Acceptable — the prompt builder runs on every internal LLM↔tool turn (multiple times per user turn), and you don't want a DB roundtrip on every iteration anyway. Pre-fetching at the entry point is faster *and* correct.

**Revisit:** Anyone writing a future graph node that needs DB access. The pattern: fetch in the entry point, hand it to state, the node reads from state.

## 2026-06-01 — gemini-2.5-flash content is `list[dict]`, not `str` — flatten before streaming

**Context:** `#11a`'s live demo broke on the chat wire format because `gemini-2.5-flash` returns `AIMessage.content` as a list of content blocks (`[{"type": "text", "text": "..."}, ...]`) when its default thinking mode is on. The plain-text streaming wire (`docs/architecture.md § "Chat wire format"`) expects a string.

**Decision:** `agent/graphs/main.py` ships `_content_to_text(content)` that flattens list-of-blocks to a concatenation of `text` parts. Used by both `arun_chat` (for the final reply) and `stream_chat` (for each streamed chunk). String inputs pass through unchanged.

**Trade-off:** Thinking-block metadata is dropped on the floor. Acceptable — the user's chat UI only renders text, and surfacing internal reasoning isn't part of the wire format. If we ever want to expose a "thinking" channel separately, that's a deliberate ticket, not a default.

**Revisit:** If we change the model to one that returns plain strings (older Gemini, or another provider), `_content_to_text` becomes a no-op but should stay — it's defensive and free.

## 2026-06-01 — user_context shape + active-on-date predicate locked by #15; reader contract pinned in data-model.md

**Context:** Same situation as `#14` for `memories`: `user_context` was empty in Atlas before `#15`, and `#15` is the first writer. Whatever shape it persists becomes the contract for `#11a` (graph node injecting active context into the prompt), `#21` (cron writers), and `#23` (dashboard readers). Critically, *how* readers query "active on date T" is also a contract — if `#11a`'s graph node and `#23`'s dashboard write different predicates, they'll show divergent context to the user.

**Decision:** Two locks. (1) The persisted shape matches `docs/data-model.md § user_context` exactly — 7 fields, no extras. Same rule as `#14`: shape changes require a decisions entry + migration plan, not silent code drift. (2) The active-on-date predicate is now pinned in `data-model.md § user_context` as the canonical contract. Every reader uses *that* predicate; if a tool needs to filter further, it composes it on top, doesn't replace it. Insert-only design choice for `#15` (no supersede, no expire) is part of this lock — the agent reconciles conflicting contexts in the prompt, not by mutating history.

**Trade-off:** Less flexibility for tools that want to "expire" or "amend" prior context. Acceptable — the same separation-of-concerns that splits read (`#13`) from consume (`#13a`) applies here: writes are dumb, the prompt does the smart reconciliation. The active-on-date predicate is also slightly verbose at every call site, but the alternative (each reader inventing its own date filter) was the actual risk.

**Revisit:** When a real-world conflict shows up — e.g. the dashboard renders two active contexts that contradict each other and the agent's reply confused the user. That's the signal that prompt reconciliation isn't enough and we need *some* tool-level conflict handling. Not before.

## 2026-06-01 — Memory write shape locked by #14; teammates should object now if at all

**Context:** Before #14, the `memories` collection was empty (the only prior insert was #13's demo, cleaned up). #14 is the first non-test writer, which means whatever shape it persists becomes the de-facto contract for #21 (cron writer), #22/#23 (frontend readers), and #13a (use_count bump). Changing the shape is cheap NOW (one tool's code, no historical rows), expensive once cron starts writing.

**Decision:** Lock the persisted shape to exactly what `docs/data-model.md § memories` describes — no extra fields, no missing fields, type-strict. #14 conforms. Any future shape addition (new field, renamed field, restructured `intervention`) requires a decisions.md entry AND a migration plan, not a silent code change.

**Trade-off:** Less flexibility for the agent to "stuff extra context" into memories. Acceptable: the prompt is what shapes the agent's writes; the schema is what shapes consumer code. Mixing them costs more than separating them.

**Revisit:** Anytime a teammate has trouble consuming the shape. The next two ramps that will pressure-test it: #21 cron (writes from a different code path) and #23 dashboard (reads structured `evidence` and `intervention`).

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
