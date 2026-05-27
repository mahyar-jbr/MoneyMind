import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";

// TODO: replace echo with backend /chat
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
  const reply = `echo: ${lastUser?.content ?? "hi"}`;

  // stream word by word so the UI feels live
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const enc = new TextEncoder();
      for (const w of reply.split(/(\s+)/)) {
        controller.enqueue(enc.encode(w));
        await new Promise((r) => setTimeout(r, 40 + Math.random() * 40));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
