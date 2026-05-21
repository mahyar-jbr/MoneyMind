# data — fixtures and demo datasets

Test data and demo CSVs. Read by both backend (ingest) and tests.

## Files

| File                  | Purpose                                                            | Status     |
| --------------------- | ------------------------------------------------------------------ | ---------- |
| `synthetic.csv`       | 6 months of realistic transactions for one demo user               | TBD (#6)   |
| `synthetic-tiny.csv`  | 30 rows, for fast pytest runs                                      | TBD (#6)   |

## CSV schema

```
date,merchant,category,amount,currency
2026-02-12,DoorDash,food.delivery,-38.42,USD
2026-02-13,Starbucks,food.coffee,-6.85,USD
2026-02-15,Direct Deposit,income.salary,2400.00,USD
```

- `date` — ISO 8601 (YYYY-MM-DD).
- `merchant` — raw merchant string from the bank.
- `category` — dot-separated taxonomy. See `docs/data-model.md`.
- `amount` — **negative for outflows, positive for inflows.** Always.
- `currency` — ISO 4217 code.

## What @kasra needs to bake into the synthetic data

The demo lives or dies on this dataset feeling real on camera. Required signals:

- **Weekly food spike on Fridays** — DoorDash ~3× the Wed average.
- **Two stress events** (Feb exam week, May busy work week) where food spend climbs above the user's baseline.
- **Payday rhythm** — direct deposit on 1st and 15th, social/discretionary spend bump in the 48 hours after each.
- **A goal-relevant pattern** — small recurring transfer to "Emergency Fund" account, paced ~12% behind target.
- **Background noise** — coffee, transit, groceries, streaming subs. Without these the data looks like a synthetic toy.

These hooks are what the agent's tools (`get_spend_anomaly`, `recall_memory`, `check_goal_pace`) detect in the demo.

## Local-only fixtures

Anything in `data/local/` is **gitignored** (see `.gitignore`). Put per-developer scratch CSVs there.
