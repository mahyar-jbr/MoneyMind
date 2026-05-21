# frontend — Next.js app

**Owner:** @aidin
**Stack:** Next.js 15 (App Router) · Tailwind · shadcn/ui · Framer Motion · Clerk

## First-time setup

Run **inside this folder**:

```bash
# 1. Scaffold Next.js into THIS folder (don't create a subfolder)
pnpm create next-app@latest . \
  --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --no-turbopack

# 2. Add the libs we'll use
pnpm add @clerk/nextjs framer-motion lucide-react
pnpm add -D @types/node

# 3. shadcn/ui
pnpm dlx shadcn@latest init
# pick: Default style, Neutral base color, CSS variables: yes

# 4. Run
pnpm dev
```

Visit http://localhost:3000 — you should see the Next.js welcome page.

## Folder conventions

| Folder        | What goes here                                                |
| ------------- | ------------------------------------------------------------- |
| `app/`        | Next.js App Router routes (`page.tsx`, `layout.tsx`, etc.)    |
| `components/` | Reusable UI components. shadcn/ui will install into `components/ui/` |
| `lib/`        | Helpers, hooks, API client, Clerk middleware glue             |
| `public/`     | Static assets (logo, fonts, images)                           |

## Env vars (read from repo-root `.env`)

This service reads from the **repo root `.env`** (`../.env`). Next.js auto-loads `.env` from the project root, but since our `.env` is one level up, you may need:

```bash
# package.json scripts
"dev": "next dev --turbo --env-file=../.env"
```

Or symlink (Mac/Linux):
```bash
ln -s ../.env .env.local
```

Variables this service uses:
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `NEXT_PUBLIC_BACKEND_URL` (defaults to http://localhost:8000)

## What ships in Sprint 1

- BACKLOG #7 — Scaffold + Clerk auth + dark theme
- BACKLOG #8 — Streaming chat shell (echo backend, no agent yet)

## Design system

Match the pitch deck (`../moneymind-pitch.html`). Dark mode only. Background `#09090b`, surface `#18181b`, accent emerald-400 `#34d399`. Inter font.
