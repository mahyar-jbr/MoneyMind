import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

// V4 — Bank-statement PDF upload with **streaming progress**.
//
// Multipart in, Server-Sent Events out. Mirrors the /api/chat proxy
// pattern: manual ReadableStream pipe so each SSE frame the backend
// emits flushes to the browser immediately, instead of being buffered
// by Vercel's Node serverless runtime.
//
// Frames pass through verbatim — the frontend parses them. The final
// frame `event: done` carries the StatementCard payload.
export const runtime = "nodejs";
// Gemini extraction can take 5-30s on a multi-page statement; default
// 10s timeout would 504 silently. 300s = Vercel Hobby ceiling.
export const maxDuration = 300;
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  // Read the multipart body once. Re-emit as a new FormData so the
  // backend gets a clean multipart payload with our headers, not
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
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      body: upstreamForm,
    });
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 502 });
  }
  if (!upstream.ok || !upstream.body) {
    const body = await upstream
      .json()
      .catch(() => ({ error: `backend ${upstream.status}` }));
    return NextResponse.json(body, { status: upstream.status });
  }

  // Manual ReadableStream pipe — same shape as the /api/chat proxy.
  // Without this, Vercel's serverless Node runtime buffers the entire
  // response body before flushing, and the user sees zero progress.
  const reader = upstream.body.getReader();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          controller.enqueue(value);
        }
      } catch (err) {
        controller.error(err);
      } finally {
        controller.close();
      }
    },
    cancel() {
      reader.cancel().catch(() => {});
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
