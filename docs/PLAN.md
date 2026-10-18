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
2. **Agent end to end, locally.** LangGraph agent in `apps/api` working through the MCP server, both running locally. See [Milestone 2 plan](#milestone-2-plan-agent-end-to-end-appsapi).
3. **Chat UI.** Simple Next.js UI, deployed to Vercel. Also deploys `apps/api` to Railway (Dockerfile, private network to the MCP server, rate limiting and daily run cap), moved here from Milestone 2.
4. **Polish and breadth.** README, example reports, more tools (SEC EDGAR, web search, GitHub).

## Milestone 2 plan: agent end to end (apps/api)

Goal: `POST /chat` on a local `apps/api` runs a LangGraph agent on Claude that calls the local MCP server's tools and answers with source URLs. Design decisions are in [DECISIONS.md](DECISIONS.md) (entries marked "Planned, M2").

### Defaults

- `apps/api` listens on `127.0.0.1:8001`; the MCP server keeps `8000`.
- Model: `ANTHROPIC_MODEL`, default `claude-opus-5-5`. Only the model ID is configurable for now.
- Settings come from environment variables, like `apps/mcp-server` (no `.env` auto-loading; use `set -a; source .env; set +a`).
- `/chat` accepts `user` and `assistant` text turns only. Earlier tool calls are not sent back; the agent re-runs tools when it needs fresh data.
- Out of scope: Docker and Railway for `apps/api`, rate limiting and the daily run cap (all Milestone 3), the structured JSON report and the orchestrator-workers graph (later, once the single loop works).

### Running both servers locally

In tmux session `startup-job`, the MCP server stays in the left pane:

```bash
cd apps/mcp-server
set -a; source .env; set +a
uv run job-research-mcp                # http://127.0.0.1:8000/mcp
```

From the right pane at the repo root, open a third pane for the API server:

```bash
tmux split-window -v -c "$PWD/apps/api"
```

In that new pane (from PR 2 on, `MCP_API_KEY` in `apps/api/.env` must equal the MCP server's):

```bash
set -a; source .env; set +a
uv run job-research-api                # http://127.0.0.1:8001
```

Commands below run in the remaining right pane, from `apps/api` with the same `.env` sourced.

### PR 1: scaffold apps/api with auth

- Scope: uv project `job-research-api` (Python 3.13), FastAPI app factory, unauthenticated `GET /health`, `API_KEY` bearer middleware copied from `apps/mcp-server` (fail closed, `AUTH_DISABLED` for local testing), entry point binding `HOST`/`PORT` (default `127.0.0.1:8001`).
- Files: `apps/api/{pyproject.toml,uv.lock,.python-version,.env.example,README.md}`, `src/job_research_api/{__init__,__main__,main,auth}.py`, `tests/{test_auth,test_health}.py`, `docs/DECISIONS.md`.
- Acceptance criteria:
  - `GET /health` returns `{"status": "ok"}` without a token.
  - Any other path returns `401` without a valid `Authorization: Bearer $API_KEY`.
  - With auth on and `API_KEY` unset, the server exits with a clear message.
  - `uv run pytest` passes with no network access.
- Test locally:
  ```bash
  cd apps/api && uv sync && uv run pytest
  cp .env.example .env && sed -i '' "s/^API_KEY=.*/API_KEY=$(openssl rand -hex 32)/" .env
  set -a; source .env; set +a      # in both the API pane and this pane
  uv run job-research-api                                              # in the API pane
  curl http://127.0.0.1:8001/health                                    # {"status":"ok"}
  curl -i http://127.0.0.1:8001/anything                               # 401
  curl -i -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8001/anything   # 404, auth passed
  API_KEY= uv run job-research-api                                    # refuses to start
  ```

### PR 2: load MCP tools at startup

- Scope: `MultiServerMCPClient` with `streamable_http` transport, `MCP_SERVER_URL` (default `http://127.0.0.1:8000/mcp`) and `Authorization: Bearer $MCP_API_KEY`. Tools load once in the FastAPI lifespan onto `app.state.tools`; startup fails with a clear message if the MCP server is down or rejects the key. An authenticated `GET /tools` lists the loaded tool names and descriptions, so the wiring is checkable before the agent exists. Adds the one opt-in integration test.
- Files: `src/job_research_api/{mcp_tools,main}.py`, `tests/test_mcp_tools.py`, `tests/test_integration.py`, `pyproject.toml` (adds `langchain-mcp-adapters`, `integration` pytest marker), `.env.example`, `README.md`, `docs/DECISIONS.md`.
- Acceptance criteria:
  - With the MCP server running, `GET /tools` lists `ping` and `get_ashby_jobs`.
  - With the MCP server stopped, or a wrong `MCP_API_KEY`, apps/api refuses to start and names the cause.
  - Unit tests use a stubbed tool loader; no network.
  - `RUN_INTEGRATION_TESTS=1 uv run pytest -m integration` loads tools from the real local MCP server and calls `ping` through the adapter (gets `"pong"`). Skipped by default.
- Test locally (MCP server running in the left pane):
  ```bash
  uv run pytest
  RUN_INTEGRATION_TESTS=1 uv run pytest -m integration
  curl -s -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8001/tools
  ```
  Then stop the MCP server (Ctrl-C in the left pane) and restart apps/api: it should refuse to start.

### PR 3: the agent graph

- Scope: `build_graph(model, tools)` returns a compiled `StateGraph(MessagesState)` with a `model` node (system prompt + `model.bind_tools(tools)`), a `ToolNode(tools)`, and a hand-written conditional edge (`tools` if the last AI message has tool calls, else `END`). The model and tools are injected, so tests pass fakes. The system prompt tells the model to cite a source URL for every fact and to say when a tool found nothing. `AGENT_RECURSION_LIMIT` (default 25) is applied on every run. No HTTP endpoint yet.
- Files: `src/job_research_api/{graph,prompts}.py`, `tests/fakes.py` (scripted fake chat model), `tests/test_graph.py`, `tests/test_integration.py` (extended), `pyproject.toml` (adds `langgraph`, `langchain-anthropic`), `docs/DECISIONS.md`.
- Acceptance criteria:
  - A scripted run of "tool call, then final answer" visits `model → tools → model → END`, and the final message contains the tool result's URL.
  - A run with no tool calls ends after one model step.
  - A model that always calls a tool stops with `GraphRecursionError` at the configured limit.
  - A tool that raises comes back to the model as an error `ToolMessage`, not a crash.
  - The integration test drives the graph with the scripted model against the real MCP server (`get_ashby_jobs` for board `ashby`) and gets a `ToolMessage` with `jobs.ashbyhq.com` URLs. Still no Claude call.
- Test locally:
  ```bash
  uv run pytest
  RUN_INTEGRATION_TESTS=1 uv run pytest -m integration
  ```

### PR 4: POST /chat (JSON)

- Scope: `POST /chat` with body `{"messages": [{"role": "user" | "assistant", "content": str}, ...]}`. Validates that the list is non-empty, ends with a `user` turn, and stays under size limits (`CHAT_MAX_MESSAGES`, `CHAT_MAX_CHARS`). Runs the graph with `ChatAnthropic(model=ANTHROPIC_MODEL)` and returns `{"message": {"role": "assistant", "content": str}, "tool_calls": [{"name": str, "args": dict}]}` (the tool calls show what the agent did). The step limit maps to `500 {"error": "step_limit"}`; Anthropic API errors map to `502 {"error": "upstream"}`. Startup fails if `ANTHROPIC_API_KEY` is unset.
- Files: `src/job_research_api/{chat,main}.py`, `tests/test_chat.py`, `.env.example` (adds `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `AGENT_RECURSION_LIMIT`), `README.md`, `docs/DECISIONS.md`.
- Acceptance criteria:
  - Unit tests override the model with the scripted fake: happy path, a conversation with earlier turns, `422` on an empty list or a trailing `assistant` turn, `401` without the key, `500` on the step limit.
  - Manual: a real question about an Ashby company returns an answer whose job facts carry `jobs.ashbyhq.com` URLs.
- Test locally (this is the only step that spends Anthropic credits):
  ```bash
  uv run pytest
  curl -s -X POST http://127.0.0.1:8001/chat \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"What engineering roles is ashby hiring for? Cite sources."}]}' | jq
  ```

### PR 5: POST /chat/stream (SSE)

- Scope: Same request body as `/chat`, response is `text/event-stream`. Events: `token` (text deltas), `tool_start` (`name`, `args`), `tool_end` (`name`, short status), `done` (final message and tool calls, same shape as `/chat`), `error`. Built on `graph.astream(stream_mode=["messages", "updates"])`. Library choice (FastAPI's own SSE support or `sse-starlette`) is made in the PR. `/chat` is unchanged.
- Files: `src/job_research_api/{stream,main}.py`, `tests/test_stream.py`, `README.md`, `docs/DECISIONS.md`.
- Acceptance criteria:
  - Unit test with the scripted fake model parses the event stream and sees `tool_start`, `tool_end`, then `token` events, then exactly one `done`.
  - The step limit and upstream errors arrive as an `error` event, and the stream closes.
  - A client disconnect cancels the run (no orphaned tool calls keep running).
- Test locally:
  ```bash
  uv run pytest
  curl -N -X POST http://127.0.0.1:8001/chat/stream \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"What engineering roles is ashby hiring for?"}]}'
  ```
  The browser's `EventSource` only does `GET`, so the Milestone 3 UI reads this stream with `fetch`.

### Done when

PR 5 is merged and, with both servers running locally, one `curl` to `/chat/stream` shows the agent calling `get_ashby_jobs` and answering with sourced facts.

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
    ├── api/                      # milestone 2 (see Milestone 2 plan for the per-PR files)
    │   ├── pyproject.toml
    │   ├── .env.example          # API_KEY, ANTHROPIC_API_KEY, MCP_SERVER_URL, MCP_API_KEY
    │   ├── src/job_research_api/
    │   │   ├── main.py           # FastAPI app, lifespan, /chat
    │   │   ├── auth.py           # API_KEY bearer middleware
    │   │   ├── mcp_tools.py      # loads MCP tools via langchain-mcp-adapters
    │   │   ├── graph.py          # model node + ToolNode loop (orchestrator-workers later)
    │   │   └── report.py         # later: report schema (every fact has a source URL)
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
