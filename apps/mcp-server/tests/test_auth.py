from collections.abc import MutableMapping
from typing import Any

import httpx
import pytest
from starlette.types import Receive, Scope, Send

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


async def _call_middleware(scope: dict[str, Any]) -> tuple[list[MutableMapping[str, Any]], list[str]]:
    """Drive BearerAuthMiddleware directly; return the messages it sent and the scope types the app saw."""
    seen: list[str] = []
    sent: list[MutableMapping[str, Any]] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope["type"])

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(message)

    await BearerAuthMiddleware(app, TEST_API_KEY)(scope, receive, send)
    return sent, seen


async def test_lifespan_passes_through() -> None:
    sent, seen = await _call_middleware({"type": "lifespan"})
    assert seen == ["lifespan"] and sent == []


async def test_websocket_without_token_is_closed_not_given_http_401() -> None:
    sent, seen = await _call_middleware({"type": "websocket", "path": "/mcp", "headers": []})
    assert seen == []
    assert sent == [{"type": "websocket.close", "code": 1008}]


async def test_websocket_to_public_path_still_needs_token() -> None:
    sent, seen = await _call_middleware({"type": "websocket", "path": "/health", "headers": []})
    assert seen == [] and sent[0]["type"] == "websocket.close"


async def test_websocket_with_token_passes_through() -> None:
    headers = [(b"authorization", f"Bearer {TEST_API_KEY}".encode())]
    sent, seen = await _call_middleware({"type": "websocket", "path": "/mcp", "headers": headers})
    assert seen == ["websocket"] and sent == []
