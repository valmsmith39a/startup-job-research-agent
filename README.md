# startup-job-research-agent

A chat agent that researches startups and their open roles. It uses Claude with live web search. It's a single Next.js app: the chat UI, the agent API, and the agent's tools all live here and deploy together on Vercel.

## Layout

| Path | What it is |
|---|---|
| `src/components/Chat.tsx` | Chat UI (client component) |
| `src/app/api/chat/route.ts` | `POST /api/chat`: streams the agent's reply as NDJSON |
| `src/lib/agent/run.ts` | Agent loop: calls Claude and turns the stream into UI events |
| `src/lib/agent/tools.ts` | Tools the agent can use (web search for now) |
| `src/lib/agent/prompt.ts` | System prompt |
| `src/lib/agent/client.ts` | Anthropic client and model |

## Local development

```bash
pnpm install
cp .env.example .env.local   # then set ANTHROPIC_API_KEY
pnpm dev
```

Open http://localhost:3000.

`ANTHROPIC_MODEL` is optional and defaults to `claude-sonnet-5-5`. `SITE_USERNAME` and `SITE_PASSWORD` set the browser login that protects the whole site (`src/proxy.ts`); the site returns 503 until both are set. Web search must be enabled for your organization in the Claude Console.

## Deployment

Pushing to `main` deploys to production through Vercel's Git integration. One-time setup:

1. In Vercel, **Add New → Project** and import this GitHub repo. Keep the Next.js preset.
2. Add `ANTHROPIC_API_KEY`, `SITE_USERNAME`, and `SITE_PASSWORD` (and optionally `ANTHROPIC_MODEL`) under **Settings → Environment Variables** for Production and Preview.
3. Deploy. After that, every push to `main` deploys to production and other branches get preview URLs.

The chat route sets `maxDuration = 300`, which needs Fluid compute. It's on by default for new Vercel projects.
