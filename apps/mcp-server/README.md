# job-research-mcp

MCP server for the Startup Job Research Agent. It serves tools over **Streamable HTTP** at `/mcp` (no stdio) and an unauthenticated `GET /health` for health checks.

Built on the official MCP Python SDK (`mcp` 2.x, where the high-level server class is `MCPServer`; it was called `FastMCP` in 1.x).

## Tools

| Tool | What it does |
|---|---|
| `ping` | Returns `"pong"`. Connectivity check. |

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd apps/mcp-server
uv sync
uv run job-research-mcp          # serves http://127.0.0.1:8000/mcp
```

`HOST` and `PORT` env vars override the bind address (defaults `127.0.0.1` and `8000`).

Quick check:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

### Test with MCP Inspector

With the server running, in another terminal:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI, set **Transport Type** to `Streamable HTTP`, **URL** to `http://127.0.0.1:8000/mcp`, click **Connect**, open **Tools**, then **List Tools** and run `ping`.

Or without the UI:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http --method tools/list
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http --method tools/call --tool-name ping
```

### Use from Claude Code

```bash
claude mcp add --transport http job-research http://127.0.0.1:8000/mcp
claude mcp list                  # job-research should show as connected
```

Then in a Claude Code session, ask it to call the `ping` tool on `job-research`.

## Tests

```bash
uv run pytest
```

Tests run the app in-process and under a real uvicorn server on a free port. They make no external network calls.
