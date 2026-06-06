import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

// Forwards the user's Clerk JWT to the backend's GET /interventions/pending,
// which returns {user_id, interventions: [...]} where each row uses backend's
// `id` field. The lib adapter (lib/interventions.ts) reshapes to the frontend
// type with `intervention_id`.
export async function GET(req: NextRequest) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const limit = req.nextUrl.searchParams.get("limit") ?? "20";
  const url = backendUrl("/interventions/pending", { limit });

  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      return NextResponse.json({ error: `backend ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 502 });
  }
}
