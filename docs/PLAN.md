# Startup Job Research Agent: Plan

## What it is

A research agent for an AI startup job search. Given a company, it researches four areas in parallel (**Funding**, **Team**, **Tech stack**, **Open roles**) and produces a structured report where every fact links to its source.

Two audiences shape every decision:

- **Recruiters** should be able to try it with no sign-up and see a great result instantly.
- **Interviewers**: every design choice should be defensible, with the rejected alternative known.

## Architecture

Monorepo with three deployable apps:

| App | Stack | Role | Deploys to |
|---|---|---|---|
| `apps/mcp-server` | Python, MCP SDK | Exposes research tools over **Streamable HTTP only** (no stdio). Usable directly by any MCP client (Claude Desktop, Claude Code, ChatGPT). | Railway (service 1) |
| `apps/api` | Python, FastAPI, LangGraph, Claude API | `/chat` endpoint running the research agent. The agent is an MCP client of `apps/mcp-server`. | Railway (service 2) |
| `apps/web` | Next.js, shadcn/ui, TypeScript (strict) | Chat UI and showcase reports. Thin client of `apps/api`. | Vercel |

### Request flow

```
Browser
  → Next.js UI (apps/web)
  → FastAPI /chat (apps/api)
  → LangGraph agent (Claude)
  → MCP server over Streamable HTTP (apps/mcp-server, Railway private network)
  → external data APIs
  ← results flow back up the same path
```

### Agent design

Orchestrator-workers pattern:

1. **Orchestrator** takes the company and plans the research.
2. **Four workers run in parallel**: Funding, Team, Tech stack, Open roles. Each calls only the MCP tools relevant to its area.
3. **Synthesizer** merges worker results into one structured JSON report.

Invariant: **every fact carries a source URL.** A fact without a source is dropped, not shown.

## Data sources (free first)

| Area | Source | Notes |
|---|---|---|
| Open roles | Ashby public job board API | No key. Greenhouse and Lever public board APIs later. |
| Funding | SEC EDGAR Form D filings | Free. Requires a `User-Agent` header with a contact email. ~10 req/s cap. |
| Team / company basics | Open YC companies dataset + web search (Tavily or Exa free tier) | |
| Tech stack | GitHub API + job posting text | |

### MCP tool rules

- One tool per capability.
- Each tool has a clear description written for the model.
- Each tool returns **trimmed, model-friendly output**, never raw API dumps.
- Each result includes the source URL(s) it came from.

## Deployment

- `apps/web` → Vercel.
- `apps/api` and `apps/mcp-server` → two services in one Railway project, talking over Railway's private network.
- Postgres (likely Supabase) **only once saved history is needed**. Not in v1.

## Security and cost

- **MCP server**: protected by an API key sent as a bearer token, known only to the agent and the owner's own MCP clients.
- **Web UI**: no login (recruiters won't sign up).
- **API**: per-IP rate limiting plus a daily cap on live runs.
- **Backstop**: monthly spend limit set in the Anthropic console.
- **Showcase**: a few pre-run example reports saved as JSON in the repo, rendered at `/reports/[slug]` with the same React components as live results. Recruiters see a great result instantly at zero cost.

## Milestones

Only the current milestone gets built.

1. **MCP server, one tool.** Ashby open roles tool, tested locally, deployed to Railway, verified from Claude Code.
2. **Agent end to end.** LangGraph agent in `apps/api` working through the deployed MCP server.
3. **Chat UI.** Simple Next.js UI, deployed to Vercel.
4. **Polish and breadth.** README, example reports, more tools (SEC EDGAR, web search, GitHub).

## Proposed repo layout

Directories appear only when their milestone starts. Target shape:

```
.
├── CLAUDE.md                     # conventions for every session
├── README.md
├── docs/
│   └── PLAN.md                   # this file
└── apps/
    ├── mcp-server/               # milestone 1
    │   ├── pyproject.toml        # uv-managed
    │   ├── uv.lock
    │   ├── .env.example          # MCP_API_KEY, PORT
    │   ├── Dockerfile            # or Railway config; decided in the M1 deploy PR
    │   ├── src/job_research_mcp/
    │   │   ├── server.py         # app, Streamable HTTP transport, bearer auth
    │   │   └── tools/
    │   │       └── ashby.py      # open roles tool (+ trimming of output)
    │   └── tests/
    │       └── test_ashby.py     # recorded/fixture responses, no live calls in CI
    ├── api/                      # milestone 2
    │   ├── pyproject.toml
    │   ├── .env.example          # ANTHROPIC_API_KEY, MCP_SERVER_URL, MCP_API_KEY
    │   ├── src/job_research_api/
    │   │   ├── main.py           # FastAPI app, /chat, rate limiting
    │   │   ├── graph.py          # orchestrator → 4 workers → synthesizer
    │   │   └── report.py         # report schema (every fact has a source URL)
    │   └── tests/
    └── web/                      # milestone 3
        ├── package.json
        ├── tsconfig.json         # strict
        ├── .env.example          # API_URL
        ├── app/
        │   ├── page.tsx          # chat
        │   └── reports/[slug]/page.tsx
        ├── components/           # shared by live results and showcase reports
        └── reports/              # milestone 4: pre-run example reports as JSON
```

Each Python app is its own uv project (no uv workspace yet) so each Railway service builds from its own directory with its own lockfile.

### Known gotcha

The root `.gitignore` is GitHub's Python template, which ignores `lib/`. shadcn/ui puts `lib/utils.ts` in the web app, so the milestone 3 PR must un-ignore `apps/web/lib/` (or scope the rule to Python).
