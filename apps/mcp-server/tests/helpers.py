from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from job_research_mcp.server import MCP_PATH
from tests.conftest import TEST_API_KEY


@asynccontextmanager
async def http_client(base_url: str, api_key: str | None = TEST_API_KEY) -> AsyncIterator[Client]:
    """An MCP client over Streamable HTTP, sending the bearer token when given."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    async with create_mcp_http_client(headers=headers) as http:
        async with Client(streamable_http_client(f"{base_url}{MCP_PATH}", http_client=http)) as client:
            yield client
