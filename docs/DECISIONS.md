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
- Tradeoff: More code than a pass-through, and the model can't answer questions that need the job description.
- Would revisit if: The agent needs description text (e.g. tech-stack extraction). Then add a separate per-job tool rather than widening this one.

## Static bearer-token middleware (Planned, PR 3)
- Decision: A small ASGI middleware requires `Authorization: Bearer <MCP_API_KEY>` on everything except `/health`, using a constant-time compare. The server refuses to start if auth is on and no key is set. `AUTH_DISABLED=true` is for local testing only.
- Why: There is one secret shared by the agent and the owner's own clients, so this is the simplest correct check. Refusing to start means a misconfigured deploy can't run open.
- Alternative rejected: The SDK's built-in auth (`TokenVerifier` + `AuthSettings`). It is built for OAuth resource servers and advertises OAuth discovery, which clients then try to follow.
- Tradeoff: No per-user identity, scopes or expiry; rotating the key means a redeploy.
- Would revisit if: Other people need their own access, or a client that only supports OAuth (e.g. a Claude Desktop custom connector) must reach the deployed server.

## Dockerfile for Railway (Planned, PR 4)
- Decision: Build `apps/mcp-server` from a Dockerfile (uv, `uv sync --frozen`, non-root, binds `0.0.0.0:$PORT`).
- Why: It builds the same way on a laptop and on Railway, and it pins the Python and uv versions.
- Alternative rejected: Railway's auto-detected builder (Railpack), which is less to write but less predictable in a monorepo subdirectory and harder to reproduce locally.
- Tradeoff: One more file to maintain, and base-image updates are on us.
- Would revisit if: Railpack's uv support makes the Dockerfile redundant, or we move off Railway.
