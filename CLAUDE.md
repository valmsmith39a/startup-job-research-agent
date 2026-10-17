# CLAUDE.md

Startup Job Research Agent: given a company, research Funding, Team, Tech stack and Open roles in parallel and produce a structured report where every fact links to its source. Full plan: [docs/PLAN.md](docs/PLAN.md).

## Layout

- `apps/mcp-server`: Python MCP server, Streamable HTTP transport only (no stdio), bearer-token auth. Railway.
- `apps/api`: FastAPI `/chat` running a LangGraph agent on the Claude API; MCP client of `apps/mcp-server`. Railway.
- `apps/web`: Next.js + shadcn/ui, thin client of `apps/api`. Vercel.

## Working style

- Small, reviewable PRs. Stop after each one for review.
- In each PR description, explain the key design choice in 2–3 sentences, including the alternative you rejected.
- Don't build ahead of the current milestone (see the Milestones section of docs/PLAN.md).
- In every PR that makes a design decision, add or update its entry in docs/DECISIONS.md in that same PR.

## Conventions

- Python: `uv` for dependencies, type hints everywhere, `pytest` for tests.
- TypeScript: `strict` mode.
- Never commit secrets. Use `.env` files (gitignored) with a committed `.env.example` per app.
- Every fact in a report carries a source URL. No source, no fact.
- MCP tools: one per capability, a clear model-facing description, trimmed model-friendly output (never raw API dumps), source URLs included.
- Tests don't hit live external APIs; use fixtures of recorded responses.
