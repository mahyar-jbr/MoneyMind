import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

// V6 — Budgets read path. Mirrors /api/goals and /api/transactions:
// Clerk JWT → backend GET /budgets → JSON pass-through. The agent's
// set_budget / abandon_budget tools are the only write paths (no POST
// /budgets exists).
export async function GET(req: NextRequest) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const status = req.nextUrl.searchParams.get("status") ?? "active";
  const limit = req.nextUrl.searchParams.get("limit") ?? "50";
  const url = backendUrl("/budgets", { status, limit });

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
