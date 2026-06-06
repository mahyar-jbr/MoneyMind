import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// force-dynamic to prevent Vercel from caching/buffering the stream.
// maxDuration covers worst-case cold ReAct loops on Vertex.
export const dynamic = "force-dynamic";
export const maxDuration = 800;

export async function POST(req: NextRequest) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return new Response("Unauthorized", { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return new Response("Unauthorized", { status: 401 });
  }

  let messages: { role: "user" | "assistant"; content: string }[] = [];
  try {
    const body = await req.json();
    messages = body.messages ?? [];
  } catch {
    return new Response("Bad JSON", { status: 400 });
  }

  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  if (!lastUser?.content) {
    return new Response("No user message", { status: 400 });
  }

  // Transparent proxy: forward to the backend /chat and pipe its plain-text
  // token stream straight through, chunk by chunk. User identity comes from
  // the Clerk JWT; no route accepts a caller-supplied user_id anymore.
  const upstream = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message: lastUser.content }),
  });

  if (!upstream.ok || !upstream.body) {
    return new Response("Agent unavailable", { status: 502 });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
