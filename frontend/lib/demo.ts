// PLACEHOLDER DATA — illustrative figures for widgets whose real source
// hasn't been built yet. Each consuming widget renders a visible "SAMPLE"
// pill so it doesn't read as real financial data.
//
// Swap targets:
//   - DEMO_BUDGETS → V6 (real Budgets feature): user-set per-category
//     monthly limits, stored in a new `budgets` Atlas collection,
//     mutated via agent tools.
//
// Dropped 2026-06-07:
//   - DEMO_NET_WORTH / DEMO_CASH_AVAILABLE — needed Plaid integration
//     to be real; not in scope for the MongoDB-track pitch.
//   - DEMO_BILLS — needed recurring-bill detection (Plaid OR ~3h of
//     heuristics over transaction history); cut for demo credibility.
//
// Dropped 2026-06-08:
//   - DEMO_GOALS / DemoGoal — replaced by V1 real goals (write_goal +
//     list_goals agent tools, backend GET /goals route, SavingsGoals
//     widget now consumes real Atlas data via /api/goals).

// monthly budget per top-level category. "used" is computed from real spend.
export const DEMO_BUDGETS: { category: string; limit: number }[] = [
  { category: "food", limit: 700 },
  { category: "shopping", limit: 500 },
  { category: "transport", limit: 250 },
  { category: "subscriptions", limit: 120 },
  { category: "health", limit: 200 },
];
