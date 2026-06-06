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

// Backend's serialized intervention doc. The repo-wide canonical shape lives in
// docs/data-model.md § interventions; backend (`api/interventions.py`)
// serializes Mongo's `_id` → `id`. We reshape to `intervention_id` here so
// the rest of the frontend stays on one name.
type BackendIntervention = {
  id: string;
  type: InterventionType;
  params: Record<string, string | number>;
  status: "pending" | "responded" | "ignored";
  user_response: InterventionResponse | null;
};

function fromBackend(doc: BackendIntervention): Intervention {
  return {
    intervention_id: doc.id,
    type: doc.type,
    params: doc.params,
    status: doc.status,
    user_response: doc.user_response,
  };
}

// GET /api/interventions/pending → backend GET /interventions/pending
// Returns the user's currently-pending intervention docs. Chat page calls
// this after every reply; it dedups before appending.
export async function fetchPendingInterventions(): Promise<Intervention[]> {
  const res = await fetch("/api/interventions/pending", { cache: "no-store" });
  if (!res.ok) return [];
  const body = (await res.json()) as { interventions?: BackendIntervention[] };
  return (body.interventions ?? []).map(fromBackend);
}

// POST /api/interventions/{id}/respond → backend POST /interventions/{id}/respond
// Backend's InterventionResponseRequest expects snake_case:
//   { user_response, modified_params }
// — NOT the camelCase the React props use. We remap here.
export async function respondToIntervention(
  interventionId: string,
  response: InterventionResponse,
  modifiedParams?: Record<string, string | number>,
): Promise<void> {
  const res = await fetch(`/api/interventions/${interventionId}/respond`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_response: response,
      modified_params: modifiedParams,
    }),
  });
  if (!res.ok) {
    throw new Error(`respond failed: ${res.status}`);
  }
}
