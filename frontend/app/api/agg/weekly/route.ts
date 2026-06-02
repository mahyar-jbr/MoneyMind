import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const sp = req.nextUrl.searchParams;
  const url = backendUrl("/agg/weekly", {
    from: sp.get("from") ?? undefined,
    to: sp.get("to") ?? undefined,
    category: sp.get("category") ?? undefined,
  });

  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: `backend ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 502 });
  }
}
