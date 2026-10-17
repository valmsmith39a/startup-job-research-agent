"""The MCP server: tool registry, health check, and the Streamable HTTP app."""

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

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


def build_app(host: str = "127.0.0.1") -> Starlette:
    """Build the ASGI app serving MCP at /mcp plus the custom routes.

    Stateless with JSON responses: every tool is a single request/response,
    so there is no per-client session to keep, and any replica can serve any
    request. `host` is passed through so the SDK can enable DNS-rebinding
    protection when bound to localhost.
    """
    return mcp.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        host=host,
    )
