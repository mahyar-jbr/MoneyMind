# Decision Log

> One entry per non-trivial choice. Three sentences each. New entries at the top.

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
