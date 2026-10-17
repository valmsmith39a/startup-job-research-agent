"""The MCP server: tool registry, health check, and the Streamable HTTP app."""

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from job_research_mcp.auth import BearerAuthMiddleware
from job_research_mcp.tools import ashby

MCP_PATH = "/mcp"

mcp = MCPServer(
    name="job-research",
    version="0.1.0",
    instructions="Tools for researching startups as potential employers.",
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness probe for Railway. Unauthenticated by design."""
    return JSONResponse({"status": "ok"})


@mcp.tool()
def ping() -> str:
    """Check that the job-research MCP server is reachable. Returns "pong"."""
    return "pong"


mcp.tool(
    name="get_ashby_jobs",
    title="Ashby open roles",
    description=ashby.DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)(ashby.get_ashby_jobs)


def build_app(*, api_key: str | None, host: str = "127.0.0.1") -> ASGIApp:
    """Build the ASGI app serving MCP at /mcp plus the custom routes.

    Stateless with JSON responses: every tool is a single request/response,
    so there is no per-client session to keep, and any replica can serve any
    request. `host` is passed through so the SDK can enable DNS-rebinding
    protection when bound to localhost.

    `api_key` is required on every request except /health; None disables
    auth (local testing only, see `auth.api_key_from_env`).
    """
    app = mcp.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        host=host,
    )
    if api_key is None:
        return app
    return BearerAuthMiddleware(app, api_key)
