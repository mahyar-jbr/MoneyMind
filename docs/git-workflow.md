# Git Workflow

> One branch per ticket. One PR per branch. Small, fast, reviewable.

## Branch naming

Format: **`<area>/<ticket-number>-<short-slug>`**

| Branch                       | Means                                         |
| ---------------------------- | --------------------------------------------- |
| `agent/9-langgraph-min`      | Mahyar on BACKLOG #9                          |
| `backend/4-csv-ingest`       | Kasra on BACKLOG #4                           |
| `frontend/7-scaffold-clerk`  | Aidin on BACKLOG #7                           |
| `agent/13-recall-memory`     | Mahyar on BACKLOG #13                         |
| `shared/30-tag-v1`           | Cross-cutting work touching multiple areas    |

Rules:

- **`<area>`** matches a top-level folder: `agent`, `backend`, `frontend`, or `shared`.
- **`<ticket-number>`** is the `#` from `BACKLOG.md`. No exceptions — if there's no ticket, don't branch.
- **`<short-slug>`** is 2–4 lowercase words, hyphen-separated. Skip "the", "and", articles.

## The flow

```
1. Pick a ticket from BACKLOG.md (your @ tag, next in priority order).
2. git checkout main && git pull
3. git checkout -b agent/9-langgraph-min
4. Code. Commit small. Push often.
5. Open a PR back to main. Title format: "feat(agent): langgraph minimum loop (#9)"
6. Get one teammate to review (👀 + 👍 in PR comments is enough — we're 3 people).
7. Merge. Delete the branch.
8. Update BACKLOG.md status.
```

## Commit messages

Conventional commits, scoped by area:

```
feat(agent):     new functionality (a new tool, a graph node)
fix(backend):    bug fix
chore(frontend): tooling, config, deps
docs:            doc-only changes
refactor:        code reorg, no behavior change
test:            tests added or changed
```

Always reference the ticket #:

```
feat(agent): langgraph minimum loop with gemini call (#9)
fix(backend): handle empty CSV uploads (#4)
chore(frontend): add shadcn-ui and dark theme tokens (#7)
```

## PR rules

- **One ticket per PR.** Don't bundle "while I was in there" changes.
- **Title:** `<type>(<area>): <what changed> (#N)` — same format as commits.
- **Body:** 3 lines — what changed, demo proof (link to screenshot / cURL / test output), any follow-up tickets needed.
- **Reviewer:** one teammate. 👍 is enough. We're 3 people on a 2-week sprint; deep code review is theatre.
- **Merge style:** **Squash and merge.** Keeps main clean. The branch's commit history dies with the branch.
- **Delete branches after merge.** GitHub has a setting to do this automatically — turn it on.

## Don't touch main directly

Even tiny doc tweaks go through a branch:

```bash
git checkout -b docs/typo-readme
# edit
git commit -am "docs: fix typo in README"
git push -u origin docs/typo-readme
# open PR, merge, delete
```

The only exception: emergency rollback during the live demo. If main breaks in the last hour before judging, push direct and apologize later.

## Stale branch policy

- A branch older than 3 days without a commit → ping the owner.
- A branch older than a week → close the PR without merging. The work is stale; re-plan from main.

## When two people touch the same file

Frontend and backend each own their folders. The contact points are:
- API contracts (defined in `docs/architecture.md`)
- Shared TypeScript types (we'll add `shared/types.ts` if needed in Sprint 2)
- `.env.example` (any new variable = update the file + ping the team)

If you're about to edit something in another person's folder, **ask first.** Not because of permissions — because they probably have something in flight.

## Quick reference (paste into Discord pinned message)

```
NEW TICKET → NEW BRANCH

  git checkout main && git pull
  git checkout -b <area>/<#>-<slug>
  # code
  git commit -m "feat(<area>): <what> (#<N>)"
  git push -u origin HEAD
  # open PR, get a 👍, squash-merge, delete branch

NEVER push to main directly.
```
