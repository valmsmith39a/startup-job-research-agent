# Design decisions

A running log of key design decisions, newest last. Each entry should take about 30 seconds to explain.

## Stateless Streamable HTTP with JSON responses (PR #2)
- Decision: Serve MCP with `stateless_http=True, json_response=True`: each request stands alone, answered with a plain JSON body.
- Why: Every tool is one request, one answer. With no session to keep, a Railway restart or a second replica drops nothing.
- Alternative rejected: The SDK's default stateful sessions with SSE streaming, which need sticky sessions and only pay off for long-running or server-initiated work.
- Tradeoff: No server-to-client notifications, progress streaming or per-session state.
- Would revisit if: A tool needs progress updates, streaming partial results, or server-initiated requests (sampling, elicitation).

## Typed, trimmed tool output (PR #3)
- Decision: `get_ashby_jobs` returns a Pydantic model, so the SDK publishes an output schema and sends `structuredContent`. Ashby's response is trimmed: descriptions, nested compensation tiers and unlisted jobs are dropped.
- Why: The agent gets a stable, documented shape instead of parsing prose, and descriptions would flood the model's context.
- Alternative rejected: A hand-built dict or formatted text (no schema, shape drifts silently), or passing Ashby's raw response through.
- Observation: With an output schema, the SDK returns the result twice: as `structuredContent` and as a serialized JSON copy in the text block, which the MCP spec recommends for clients that only read text.
- Tradeoff: More code than a pass-through, and the model can't answer questions that need the job description. Depending on the client, the model may get both copies, roughly doubling tokens per call.
- Would revisit if: The agent needs description text (e.g. tech-stack extraction); then add a separate per-job tool rather than widening this one. Or if token cost or context size becomes a problem; then keep `structuredContent` as the real data and return a short text summary instead of the full copy (e.g. "27 matching jobs at Ashby out of 63").

## Static bearer-token middleware (PR #4)
- Decision: A small pure-ASGI middleware requires `Authorization: Bearer <MCP_API_KEY>` on everything except `/health` (constant-time compare). With auth on and no key, the server refuses to start. `AUTH_DISABLED=true` is for local testing only and is refused unless `HOST` is loopback (PR #5). Only lifespan events pass through unchecked; a websocket without a token is closed.
- Why: One shared secret between the agent and the owner's own clients needs nothing more. Failing at startup means a misconfigured deploy can't run open, including a stray `AUTH_DISABLED` variable on a container bound to `0.0.0.0`.
- Alternative rejected: The SDK's built-in auth (`TokenVerifier` + `AuthSettings`). It is shaped for OAuth resource servers (issuer URL, protected-resource metadata) and advertises OAuth discovery, which clients then try to follow.
- Tradeoff: No per-user identity, scopes or expiry. Rotating the key means updating every client. Claude Desktop custom connectors can't send custom headers, so they need `AUTH_DISABLED` locally.
- Would revisit if: Other people need their own access, or an OAuth-only client (e.g. a Claude Desktop custom connector) must reach the deployed server.

## Dockerfile for Railway (PR #5)
- Decision: Build `apps/mcp-server` from a multi-stage Dockerfile: uv pinned from its official image, `uv sync --frozen --no-dev`, a slim non-root runtime that binds `0.0.0.0:$PORT`. `railway.json` adds a `/health` healthcheck and limits redeploys to `apps/mcp-server/**`.
- Why: It builds the same image on a laptop and on Railway, pins the Python and uv versions, and installs exactly what `uv.lock` says.
- Alternative rejected: Railway's auto-detected builder (Railpack). Less to write, but less predictable in a monorepo subdirectory and harder to reproduce locally.
- Tradeoff: Two more files to maintain, and keeping the base image and uv version up to date is on us.
- Would revisit if: Railpack's uv support makes the Dockerfile redundant, or we move off Railway.

## Hand-written LangGraph StateGraph (Planned, M2 PR 3)
- Decision: Build the agent as an explicit `StateGraph` over `MessagesState`: a `model` node (Claude with the MCP tools bound), a `ToolNode`, and a conditional edge that loops back to `tools` while the last AI message has tool calls and ends otherwise. Every run sets `recursion_limit` (env `AGENT_RECURSION_LIMIT`, default 25).
- Why: The control flow is visible in about 30 lines, so it can be explained and tested node by node, and it is the shape the orchestrator-workers design later grows from (more nodes, same graph). The recursion limit caps cost when the model keeps calling tools.
- Alternative rejected: The prebuilt agent (`create_react_agent` in `langgraph.prebuilt`, superseded by `langchain.agents.create_agent`). Same loop in one call, but it hides the graph, and customizing it means learning its hook API instead of editing a node.
- Tradeoff: More code to own than the one-liner. Milestone 2 is a single tool-calling loop, not yet the orchestrator, four parallel workers and synthesizer described in PLAN.md.
- Would revisit if: The single loop is good enough on real companies (then keep it), or more tools land in Milestone 4 (then split into the parallel workers).

## MCP tools through langchain-mcp-adapters, loaded once (Planned, M2 PR 2)
- Decision: Use `MultiServerMCPClient` from `langchain-mcp-adapters` with the `streamable_http` transport and an `Authorization: Bearer $MCP_API_KEY` header. Call `get_tools()` once in the FastAPI lifespan and keep the tools on `app.state`. If the MCP server is unreachable or rejects the key, apps/api refuses to start.
- Why: The adapter turns MCP tool schemas into LangChain tools that `bind_tools` and `ToolNode` accept as they are. Loading at startup keeps tool discovery off the request path, and failing at startup surfaces a wrong URL or key immediately instead of on the first chat.
- Alternative rejected: The `mcp` SDK's `ClientSession` with hand-written conversion to LangChain tools (more code, same result), or listing tools on every request (an extra round trip per chat).
- Tradeoff: The tool list is fixed until apps/api restarts. Each tool call still opens its own short MCP session, which suits the stateless server. The adapter currently pins `mcp<2`, while apps/mcp-server runs `mcp` 2.x; that is fine over the wire because they are separate uv projects, but both versions need watching.
- Would revisit if: Tools change while apps/api is running, or the adapter lags the protocol.

## Stateless /chat, JSON first (Planned, M2 PR 4 and 5)
- Decision: `POST /chat` takes the full message history (`user` and `assistant` text turns) on every request and returns the assistant's reply as JSON. Server-Sent Events streaming comes later as a separate `POST /chat/stream`; `/chat` stays JSON.
- Why: No conversation store, so no database and no session affinity (PLAN.md defers Postgres). JSON first means the agent can be tested with curl and plain pytest before streaming adds event framing.
- Alternative rejected: Server-side conversation state (LangGraph checkpointer keyed by a thread ID), which needs persistence to survive restarts, and streaming from the first PR.
- Tradeoff: Request size grows with the conversation, and the client can rewrite history. Tool calls and tool results from earlier turns are not sent back, so the model sees only the text of earlier answers.
- Would revisit if: Saved history is needed (then a checkpointer on Postgres), or conversations get long enough for request size to matter.

## Separate API_KEY for apps/api, same fail-closed middleware (Planned, M2 PR 1)
- Decision: apps/api requires `Authorization: Bearer <API_KEY>` on everything except `/health`, using a copy of the MCP server's pure-ASGI middleware: constant-time compare, refuse to start when auth is on and the key is missing, `AUTH_DISABLED=true` for local testing only. `API_KEY` and `MCP_API_KEY` are different secrets.
- Why: Two secrets keep the blast radius small: the web app's key (Milestone 3) can't reach the MCP server directly. Reusing the pattern means one auth design to explain.
- Alternative rejected: Reusing `MCP_API_KEY` for both services, or extracting the middleware into a shared package (it is about 60 lines, and a shared package would complicate each app's own uv project and Railway build).
- Tradeoff: Two copies of the middleware can drift. The browser can't hold a secret, so in Milestone 3 the Next.js server, not the browser, sends `API_KEY`.
- Would revisit if: A third Python service needs the same middleware (then a shared package), or real users need their own access.

## Local-first Milestone 2 (Planned, M2)
- Decision: apps/api runs on `127.0.0.1:8001` and talks to the local MCP server at `http://127.0.0.1:8000/mcp`. Docker, Railway, rate limiting and the daily run cap for apps/api move to Milestone 3.
- Why: The agent loop is the risk in this milestone. Running both servers locally gives the fastest feedback, and deployment is already proven by the MCP server in Milestone 1.
- Alternative rejected: Deploying apps/api to Railway in this milestone, which adds a second deploy before the agent works.
- Tradeoff: Milestone 2 ends without a live URL. Milestone 3 gets bigger (deploy the API and the web app).
- Would revisit if: Someone needs to try the agent before the UI exists.

## Fake chat model in unit tests (Planned, M2 PR 3)
- Decision: Unit tests never call the Claude API. They inject a scripted fake chat model (a small subclass of LangChain's `GenericFakeChatModel` whose `bind_tools` returns itself) that emits predefined AI messages, including tool calls. One opt-in integration test, skipped unless `RUN_INTEGRATION_TESTS=1`, drives the graph with the same scripted model against the real local MCP server.
- Why: Tests stay free, fast and deterministic, and the graph's routing is tested exactly. The integration test proves the MCP wiring end to end without spending tokens.
- Alternative rejected: Recorded Claude responses (VCR-style cassettes), which break whenever the prompt or tools change, or live Claude calls in CI (cost, flakiness, secrets in CI).
- Tradeoff: No automated test checks what Claude actually does with the tools; that stays a manual curl check.
- Would revisit if: Prompt quality needs regression coverage; then add a small, opt-in eval set rather than live calls in unit tests.
