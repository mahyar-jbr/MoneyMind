// shapes returned by the backend (see backend/app/api)
export type WeekBucket = {
  week: string; // YYYY-MM-DD, start of week
  by_category: Record<string, number>;
  total_spend: number;
};

export type WeeklyResponse = {
  user_id: string;
  weeks: WeekBucket[];
};

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
