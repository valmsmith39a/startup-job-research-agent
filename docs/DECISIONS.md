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
- Decision: A small pure-ASGI middleware requires `Authorization: Bearer <MCP_API_KEY>` on everything except `/health` (constant-time compare). With auth on and no key, the server refuses to start. `AUTH_DISABLED=true` is for local testing only.
- Why: One shared secret between the agent and the owner's own clients needs nothing more. Failing at startup means a misconfigured deploy can't run open.
- Alternative rejected: The SDK's built-in auth (`TokenVerifier` + `AuthSettings`). It is shaped for OAuth resource servers (issuer URL, protected-resource metadata) and advertises OAuth discovery, which clients then try to follow.
- Tradeoff: No per-user identity, scopes or expiry. Rotating the key means updating every client. Claude Desktop custom connectors can't send custom headers, so they need `AUTH_DISABLED` locally.
- Would revisit if: Other people need their own access, or an OAuth-only client (e.g. a Claude Desktop custom connector) must reach the deployed server.

## Dockerfile for Railway (PR #5)
- Decision: Build `apps/mcp-server` from a multi-stage Dockerfile: uv pinned from its official image, `uv sync --frozen --no-dev`, a slim non-root runtime that binds `0.0.0.0:$PORT`. `railway.json` adds a `/health` healthcheck and limits redeploys to `apps/mcp-server/**`.
- Why: It builds the same image on a laptop and on Railway, pins the Python and uv versions, and installs exactly what `uv.lock` says.
- Alternative rejected: Railway's auto-detected builder (Railpack). Less to write, but less predictable in a monorepo subdirectory and harder to reproduce locally.
- Tradeoff: Two more files to maintain, and keeping the base image and uv version up to date is on us.
- Would revisit if: Railpack's uv support makes the Dockerfile redundant, or we move off Railway.
