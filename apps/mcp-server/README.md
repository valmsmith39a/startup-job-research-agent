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
export MCP_API_KEY=$(openssl rand -hex 32)
uv run job-research-mcp          # serves http://127.0.0.1:8000/mcp
```

### Configuration

| Env var | Default | Meaning |
|---|---|---|
| `MCP_API_KEY` | (none) | Required bearer token for `/mcp`. The server refuses to start if auth is on and this is unset. |
| `AUTH_DISABLED` | `false` | `true` turns auth off. **Local testing only**, e.g. trying the server as a Claude Desktop custom connector, which supports OAuth or no auth but not custom headers. |
| `HOST` | `127.0.0.1` | Bind address. |
| `PORT` | `8000` | Bind port. |

See [`.env.example`](.env.example). The server reads real environment variables; it does not load `.env` itself (use `set -a; source .env; set +a`).

### Auth

Every request except `GET /health` needs `Authorization: Bearer $MCP_API_KEY`; anything else gets `401`.

```bash
curl http://127.0.0.1:8000/health                       # {"status":"ok"}, no token needed
curl -i -X POST http://127.0.0.1:8000/mcp               # 401
```

Without the header, MCP clients see the `401` and may try OAuth discovery (the Inspector reports "auth required"); that means the token is missing, not that the server wants OAuth.

### Test with MCP Inspector

With the server running, in another terminal:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI, set **Transport Type** to `Streamable HTTP` and **URL** to `http://127.0.0.1:8000/mcp`. Under **Authentication**, add a header `Authorization` with value `Bearer <your MCP_API_KEY>`. Click **Connect**, open **Tools**, then **List Tools** and run `get_ashby_jobs`.

Or without the UI:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http \
  --header "Authorization: Bearer $MCP_API_KEY" --method tools/list
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http \
  --header "Authorization: Bearer $MCP_API_KEY" \
  --method tools/call --tool-name get_ashby_jobs --tool-arg company=ashby --tool-arg keyword=engineer
```

### Use from Claude Code

```bash
claude mcp add --transport http job-research http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer $MCP_API_KEY"
claude mcp list                  # job-research: ... (HTTP) - ✓ Connected
```

If you registered it earlier without the header, run `claude mcp remove job-research` first.

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
