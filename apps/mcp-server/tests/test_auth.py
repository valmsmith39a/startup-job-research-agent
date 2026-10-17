import httpx
import pytest

from job_research_mcp.auth import AuthConfigError, BearerAuthMiddleware, api_key_from_env
from job_research_mcp.server import MCP_PATH
from tests.conftest import TEST_API_KEY
from tests.helpers import http_client

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def post_mcp(base_url: str, authorization: str | None) -> httpx.Response:
    headers = dict(MCP_HEADERS)
    if authorization is not None:
        headers["Authorization"] = authorization
    return httpx.post(f"{base_url}{MCP_PATH}", json=INITIALIZE, headers=headers)


def test_missing_header_is_401(server_url: str) -> None:
    response = post_mcp(server_url, None)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert response.json()["error"] == "unauthorized"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer wrong-key", f"Basic {TEST_API_KEY}", TEST_API_KEY, "Bearer", f"Bearer {TEST_API_KEY}x"],
)
def test_wrong_credentials_are_401(server_url: str, authorization: str) -> None:
    assert post_mcp(server_url, authorization).status_code == 401


@pytest.mark.parametrize("authorization", [f"Bearer {TEST_API_KEY}", f"bearer {TEST_API_KEY}"])
def test_right_token_is_accepted(server_url: str, authorization: str) -> None:
    response = post_mcp(server_url, authorization)
    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "job-research"


async def test_mcp_client_with_token_can_call_tools(server_url: str) -> None:
    async with http_client(server_url) as client:
        result = await client.call_tool("ping", {})
    assert not result.is_error


def test_health_needs_no_token(server_url: str) -> None:
    assert httpx.get(f"{server_url}/health").status_code == 200


def test_auth_disabled_accepts_requests_without_token(open_server_url: str) -> None:
    assert post_mcp(open_server_url, None).status_code == 200


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"MCP_API_KEY": "abc"}, "abc"),
        ({"MCP_API_KEY": "  abc  "}, "abc"),
        ({"AUTH_DISABLED": "true"}, None),
        ({"AUTH_DISABLED": "TRUE", "MCP_API_KEY": "abc"}, None),
        ({"AUTH_DISABLED": "false", "MCP_API_KEY": "abc"}, "abc"),
    ],
)
def test_api_key_from_env(environ: dict[str, str], expected: str | None) -> None:
    assert api_key_from_env(environ) == expected


@pytest.mark.parametrize("environ", [{}, {"MCP_API_KEY": ""}, {"MCP_API_KEY": "   "}, {"AUTH_DISABLED": "false"}])
def test_auth_on_without_key_refuses_to_start(environ: dict[str, str]) -> None:
    with pytest.raises(AuthConfigError, match="MCP_API_KEY is not set"):
        api_key_from_env(environ)


def test_middleware_rejects_empty_key() -> None:
    with pytest.raises(ValueError):
        BearerAuthMiddleware(app=lambda scope, receive, send: None, api_key="")  # type: ignore[arg-type,return-value]
