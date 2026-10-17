# job-research-mcp

MCP server for the Startup Job Research Agent. It serves tools over **Streamable HTTP** at `/mcp` (no stdio) and an unauthenticated `GET /health` for health checks.

Built on the official MCP Python SDK (`mcp` 2.x, where the high-level server class is `MCPServer`; it was called `FastMCP` in 1.x).

## Tools

| Tool | What it does |
|---|---|
| `ping` | Returns `"pong"`. Connectivity check. |
| `get_ashby_jobs` | A company's listed open roles from its public Ashby job board (`company` = board slug or `jobs.ashbyhq.com` URL; optional `keyword` title filter and `remote_only`). Returns trimmed jobs with job/apply URLs and the board's `source_url`; descriptions are dropped. |

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
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http \
  --method tools/call --tool-name get_ashby_jobs --tool-arg company=ashby --tool-arg keyword=engineer
```

### Use from Claude Code

```bash
claude mcp add --transport http job-research http://127.0.0.1:8000/mcp
claude mcp list                  # job-research should show as connected
```

Then in a Claude Code session, ask for example: "Use get_ashby_jobs to list open engineering roles at ashby". Board names are case-sensitive; take the slug from the company's `jobs.ashbyhq.com/<board>` URL.

## Tests

```bash
uv run pytest
```

Tests run the app in-process and under a real uvicorn server on a free port. They make no external network calls: Ashby responses are mocked with respx from `tests/fixtures/ashby_board.json`, a fixture built from Ashby's documented response shape.

One optional smoke test hits the real Ashby API and is skipped by default:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live                          # board "ashby"
RUN_LIVE_TESTS=1 ASHBY_LIVE_BOARD=<board> uv run pytest -m live
```
