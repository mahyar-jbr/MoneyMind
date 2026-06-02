// server-side helper: builds backend urls. user identity rides as a clerk jwt
// (Authorization: Bearer) on the request, not a query param (#4a).
const BASE =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  "http://localhost:8000";

export function backendUrl(
  path: string,
  params: Record<string, string | undefined> = {},
) {
  const url = new URL(path, BASE);
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== "") url.searchParams.set(key, value);
  }
  return url.toString();
}
