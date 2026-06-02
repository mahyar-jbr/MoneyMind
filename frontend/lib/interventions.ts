export type InterventionType = "cap" | "reminder" | "swap_suggestion" | "reflection";
export type InterventionResponse = "accepted" | "declined" | "modified" | "ignored";

// matches the pending doc #17 writes to atlas.interventions
export type Intervention = {
  intervention_id: string;
  type: InterventionType;
  params: Record<string, string | number>;
  status: "pending" | "responded" | "ignored";
  user_response: InterventionResponse | null;
};

type Copy = { title: string; body: string; cta: string };

const COPY: Record<InterventionType, (p: Record<string, string | number>) => Copy> = {
  reminder: (p) => ({
    title: "Set a weekly reminder",
    body: `I can nudge you every ${p.day ?? "Sunday"} about ${p.what ?? "meal prep"}.`,
    cta: "Set reminder",
  }),
  cap: (p) => ({
    title: "Set a spending cap",
    body: `Hold ${p.category ?? "this category"} to ${p.limit ?? "a weekly limit"}.`,
    cta: "Set cap",
  }),
  swap_suggestion: (p) => ({
    title: "Try a swap",
    body: `Trading ${p.from ?? "delivery"} for ${p.to ?? "groceries"} would free up room in your budget.`,
    cta: "Sounds good",
  }),
  reflection: (p) => ({
    title: "A quick reflection",
    body: String(p.prompt ?? "Want to talk through what drove this week's spend?"),
    cta: "Okay",
  }),
};

export function interventionCopy(it: Intervention): Copy {
  return COPY[it.type](it.params);
}

// the user's pending interventions. mock for now: serves one, then nothing.
// swap the body for a GET when the backend exposes a pending list; the chat
// page already polls this after each turn.
let served = false;
export async function fetchPendingInterventions(): Promise<Intervention[]> {
  if (served) return [];
  served = true;
  return [
    {
      intervention_id: `iv_${Math.random().toString(36).slice(2, 8)}`,
      type: "reminder",
      params: { day: "Sunday", what: "meal prep" },
      status: "pending",
      user_response: null,
    },
  ];
}

// records the user's choice. swap the body for a POST when the endpoint lands:
// POST /interventions/{id}/respond  { response, modified_params }
export async function respondToIntervention(
  interventionId: string,
  response: InterventionResponse,
  modifiedParams?: Record<string, string | number>,
): Promise<void> {
  void [interventionId, response, modifiedParams];
  await new Promise((r) => setTimeout(r, 200));
}
