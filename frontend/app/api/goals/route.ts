import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

// V1 — Goals read path. Mirrors /api/transactions and /api/interventions:
// Clerk JWT → backend GET /goals → JSON pass-through. The agent's
// write_goal tool is the only write path (no POST /goals exists).
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
  const limit = req.nextUrl.searchParams.get("limit") ?? "20";
  const url = backendUrl("/goals", { status, limit });

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
