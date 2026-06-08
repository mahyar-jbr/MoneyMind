// shapes returned by the backend (see backend/app/api)

export type Transaction = {
  user_id: string;
  date: string; // YYYY-MM-DD
  merchant: string;
  merchant_canonical: string;
  category: string;
  amount: number; // negative for spend
  currency: string;
  source: string;
  raw: Record<string, unknown>;
};

export type TransactionsResponse = {
  user_id: string;
  transactions: Transaction[];
};

export type InboxMessage = {
  id: string;
  user_id: string;
  type: "weekly_summary" | "reminder";
  title: string;
  body: string;
  created_at: string; // ISO timestamp
  metadata: Record<string, unknown>;
};

export type InboxResponse = {
  user_id: string;
  messages: InboxMessage[];
};

export type Goal = {
  id: string;
  user_id: string;
  title: string;
  target_amount: number;
  current_amount: number;
  target_date: string; // ISO datetime
  pace_check: "weekly";
  status: "active" | "paused" | "complete" | "abandoned";
  created_at: string; // ISO datetime
};

export type GoalsResponse = {
  user_id: string;
  goals: Goal[];
};

export type Budget = {
  id: string;
  user_id: string;
  category: string;
  limit: number;
  period: "month";
  status: "active" | "abandoned";
  created_at: string;
  updated_at: string;
};

export type BudgetsResponse = {
  user_id: string;
  budgets: Budget[];
};

export type IngestStatementResponse = {
  inserted: number;
  duplicate_of_prior_upload: boolean;
  issuer: string;
  account_last4: string;
  period_start: string | null;
  period_end: string | null;
  total_spend: number;
  by_category: Record<string, number>;
  payment_count: number;
  payment_total: number;
  warnings: string[];
  source: string;
};
