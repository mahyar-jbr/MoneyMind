// DEMO PLACEHOLDER DATA.
// The backend only stores transactions, so these widgets (net worth, cash,
// budgets, goals, bills) show illustrative figures for the product walkthrough
// and are tagged "demo" in the UI. Swap for real sources when they exist:
// account linking (balances), user-set budgets, the goals collection, and
// recurring-bill detection.

export const DEMO_NET_WORTH = 82400;
export const DEMO_CASH_AVAILABLE = 6230;

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

export type DemoBill = { name: string; amount: number; dueInDays: number };
export const DEMO_BILLS: DemoBill[] = [
  { name: "Rent", amount: 1850, dueInDays: 4 },
  { name: "Credit card", amount: 420, dueInDays: 9 },
  { name: "Hydro + internet", amount: 165, dueInDays: 12 },
  { name: "Phone", amount: 55, dueInDays: 18 },
];
