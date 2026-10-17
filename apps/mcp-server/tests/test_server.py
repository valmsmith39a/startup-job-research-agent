import httpx
from mcp import Client

from job_research_mcp.server import MCP_PATH, mcp


def test_health_is_ok(server_url: str) -> None:
    response = httpx.get(f"{server_url}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ping_in_process() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert "ping" in [tool.name for tool in tools.tools]
        result = await client.call_tool("ping", {})
    assert not result.is_error
    assert result.structured_content == {"result": "pong"}


async def test_ping_over_streamable_http(server_url: str) -> None:
    async with Client(f"{server_url}{MCP_PATH}") as client:
        result = await client.call_tool("ping", {})
    assert not result.is_error
    assert result.structured_content == {"result": "pong"}
