// PLACEHOLDER DATA — illustrative figures for widgets whose real source
// hasn't been built yet. Each consuming widget renders a visible "SAMPLE"
// pill so it doesn't read as real financial data.
//
// Swap targets:
//   - DEMO_BUDGETS → V6 (real Budgets feature): user-set per-category
//     monthly limits, stored in a new `budgets` Atlas collection,
//     mutated via agent tools.
//   - DEMO_GOALS → V1 (Goals): write_goal + list_goals agent tools,
//     backend GET /goals route, dashboard widget swap.
//
// Dropped 2026-06-07:
//   - DEMO_NET_WORTH / DEMO_CASH_AVAILABLE — needed Plaid integration
//     to be real; not in scope for the MongoDB-track pitch.
//   - DEMO_BILLS — needed recurring-bill detection (Plaid OR ~3h of
//     heuristics over transaction history); cut for demo credibility.

// monthly budget per top-level category. "used" is computed from real spend.
export const DEMO_BUDGETS: { category: string; limit: number }[] = [
  { category: "food", limit: 700 },
  { category: "shopping", limit: 500 },
  { category: "transport", limit: 250 },
  { category: "subscriptions", limit: 120 },
  { category: "health", limit: 200 },
];

export type DemoGoal = { name: string; target: number; saved: number };
export const DEMO_GOALS: DemoGoal[] = [
  { name: "Emergency fund", target: 10000, saved: 6400 },
  { name: "Japan trip", target: 3000, saved: 1840 },
  { name: "New laptop", target: 2200, saved: 700 },
];
