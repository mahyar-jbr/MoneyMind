import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
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
  // token stream straight through, chunk by chunk. user_id rides as a query
  // param until #9a/#4a swap to a Clerk JWT. Wire format: text/plain chunked.
  const upstream = await fetch(
    `${BACKEND_URL}/chat?user_id=${encodeURIComponent(userId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: lastUser.content }),
    },
  );

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
