import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

// V4 — Bank-statement PDF upload. Multimodal Gemini on the backend
// extracts transactions + categorizes them + bulk-writes to Atlas.
// The agent's tools read those rows on the next chat turn (no separate
// agent-side ingest tool — by design).
//
// Multipart pass-through: we forward the raw FormData body to the
// backend with the user's Clerk JWT. Vercel's Node runtime preserves
// the multipart boundary if we re-emit the body as-is.
export const runtime = "nodejs";
// Bank PDFs are tiny but Gemini's extraction call can take 5-30s on a
// busy multi-page statement; default 10s would 504.
export const maxDuration = 300;

export async function POST(req: NextRequest) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  // Read the multipart body once. We re-emit it as a new FormData so the
  // backend receives a clean multipart payload with our headers, not
  // Next's framework-mangled version.
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "expected multipart/form-data with a `file` field" },
      { status: 400 },
    );
  }
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "missing or invalid `file` form field" },
      { status: 400 },
    );
  }

  const upstreamForm = new FormData();
  upstreamForm.append("file", file, file.name);

  const url = backendUrl("/ingest/statement");
  try {
    const res = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      body: upstreamForm,
    });
    const body = await res.json().catch(() => ({ error: "backend returned non-JSON" }));
    if (!res.ok) {
      return NextResponse.json(body, { status: res.status });
    }
    return NextResponse.json(body);
  } catch {
    return NextResponse.json(
      { error: "backend unreachable" },
      { status: 502 },
    );
  }
}
