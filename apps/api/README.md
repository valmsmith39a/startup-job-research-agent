# job-research-api

FastAPI service for the Startup Job Research Agent. In Milestone 2 it grows a LangGraph agent behind `POST /chat` that calls the tools of [`apps/mcp-server`](../mcp-server/README.md). So far it serves only an unauthenticated `GET /health` and bearer-token auth on every other path.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd apps/api
uv sync
cp .env.example .env && sed -i '' "s/^API_KEY=.*/API_KEY=$(openssl rand -hex 32)/" .env   # macOS sed; on Linux use sed -i
set -a; source .env; set +a
uv run job-research-api          # serves http://127.0.0.1:8001
```

### Configuration

| Env var | Default | Meaning |
|---|---|---|
| `API_KEY` | (none) | Required bearer token for every path except `/health`. The server refuses to start if auth is on and this is unset. A different secret from the MCP server's `MCP_API_KEY`. |
| `AUTH_DISABLED` | `false` | `true` turns auth off. **Local testing only.** The server refuses to start with it unless `HOST` is `127.0.0.1`, `localhost` or `::1`. |
| `HOST` | `127.0.0.1` | Bind address. |
| `PORT` | `8001` | Bind port (the MCP server uses `8000`). |

See [`.env.example`](.env.example). The server reads real environment variables; it does not load `.env` itself (use `set -a; source .env; set +a`).

### Auth

Every request except `GET /health` needs `Authorization: Bearer $API_KEY`; anything else gets `401`. The middleware is a copy of the MCP server's (see `docs/DECISIONS.md`).

```bash
curl http://127.0.0.1:8001/health                                            # {"status":"ok"}
curl -i http://127.0.0.1:8001/anything                                       # 401
curl -i -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8001/anything   # 404, auth passed
```

## Tests

```bash
uv run pytest
```

Tests use FastAPI's in-process `TestClient` and stub `uvicorn.run` for the startup checks, so nothing binds a port and nothing touches the network.
