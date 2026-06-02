// server-side helper: builds backend urls and picks which user to query.
// the backend has no auth yet, so we pass a seeded demo user. swap DEMO_USER_ID
// for a real clerk -> user_id lookup once the backend supports it.
const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const DEMO_USER_ID = process.env.DEMO_USER_ID ?? "u_482";

export function backendUrl(
  path: string,
  params: Record<string, string | undefined> = {},
) {
  const url = new URL(path, BASE);
  url.searchParams.set("user_id", DEMO_USER_ID);
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== "") url.searchParams.set(key, value);
  }
  return url.toString();
}
