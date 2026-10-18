"""Bearer auth and the startup checks. Adapted from apps/mcp-server's test_auth.py and test_main.py."""

from collections.abc import Iterator, MutableMapping
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from job_research_api import __main__ as entry
from job_research_api.auth import AuthConfigError, BearerAuthMiddleware, api_key_from_env
from job_research_api.main import create_app

TEST_API_KEY = "test-key-0123456789"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(api_key=TEST_API_KEY)) as client:
        yield client


# --- HTTP requests through the real app ---


def test_missing_header_is_401(client: TestClient) -> None:
    response = client.get("/anything")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert response.json()["error"] == "unauthorized"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer wrong-key", f"Basic {TEST_API_KEY}", TEST_API_KEY, "Bearer", f"Bearer {TEST_API_KEY}x"],
)
def test_wrong_credentials_are_401(client: TestClient, authorization: str) -> None:
    assert client.get("/anything", headers={"Authorization": authorization}).status_code == 401


@pytest.mark.parametrize("authorization", [f"Bearer {TEST_API_KEY}", f"bearer {TEST_API_KEY}"])
def test_right_token_passes_auth(client: TestClient, authorization: str) -> None:
    # No route at /anything yet, so passing auth means reaching FastAPI's 404.
    assert client.get("/anything", headers={"Authorization": authorization}).status_code == 404


def test_docs_need_a_token(client: TestClient) -> None:
    for path in ("/docs", "/openapi.json"):
        assert client.get(path).status_code == 401


def test_auth_disabled_accepts_requests_without_token() -> None:
    with TestClient(create_app(api_key=None)) as client:
        assert client.get("/anything").status_code == 404


# --- api_key_from_env ---


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"API_KEY": "abc"}, "abc"),
        ({"API_KEY": "  abc  "}, "abc"),
        ({"AUTH_DISABLED": "true"}, None),
        ({"AUTH_DISABLED": "TRUE", "API_KEY": "abc"}, None),
        ({"AUTH_DISABLED": "false", "API_KEY": "abc"}, "abc"),
    ],
)
def test_api_key_from_env(environ: dict[str, str], expected: str | None) -> None:
    assert api_key_from_env(environ) == expected


@pytest.mark.parametrize(
    "environ",
    [{}, {"API_KEY": ""}, {"API_KEY": "   "}, {"AUTH_DISABLED": "false"}, {"MCP_API_KEY": "abc"}],
)
def test_auth_on_without_key_raises(environ: dict[str, str]) -> None:
    with pytest.raises(AuthConfigError, match="API_KEY is not set"):
        api_key_from_env(environ)


# --- the middleware on its own: lifespan and websocket scopes ---


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
    sent, seen = await _call_middleware({"type": "websocket", "path": "/chat", "headers": []})
    assert seen == []
    assert sent == [{"type": "websocket.close", "code": 1008}]


async def test_websocket_to_public_path_still_needs_token() -> None:
    sent, seen = await _call_middleware({"type": "websocket", "path": "/health", "headers": []})
    assert seen == [] and sent[0]["type"] == "websocket.close"


async def test_websocket_with_token_passes_through() -> None:
    headers = [(b"authorization", f"Bearer {TEST_API_KEY}".encode())]
    sent, seen = await _call_middleware({"type": "websocket", "path": "/chat", "headers": headers})
    assert seen == ["websocket"] and sent == []


# --- startup checks in __main__.main (uvicorn.run is stubbed; nothing binds) ---


@pytest.fixture
def run_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: calls.append(kwargs))
    for name in ("API_KEY", "AUTH_DISABLED", "HOST", "PORT"):
        monkeypatch.delenv(name, raising=False)
    return calls


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "10.0.0.5", "myservice.up.railway.app"])
def test_auth_disabled_on_non_loopback_host_refuses_to_start(
    monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]], host: str
) -> None:
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("HOST", host)
    with pytest.raises(SystemExit, match="AUTH_DISABLED=true is only allowed on a loopback HOST"):
        entry.main()
    assert run_calls == []


def test_auth_disabled_wins_over_a_set_key_and_still_refuses_on_public_host(
    monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]]
) -> None:
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("API_KEY", "abc")
    monkeypatch.setenv("HOST", "0.0.0.0")
    with pytest.raises(SystemExit):
        entry.main()
    assert run_calls == []


@pytest.mark.parametrize("host", [None, "127.0.0.1", "localhost", "::1"])
def test_auth_disabled_on_loopback_host_starts(
    monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]], host: str | None
) -> None:
    monkeypatch.setenv("AUTH_DISABLED", "true")
    if host is not None:
        monkeypatch.setenv("HOST", host)
    entry.main()
    assert run_calls == [{"host": host or "127.0.0.1", "port": 8001}]


def test_auth_on_with_key_starts_on_any_host(monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]]) -> None:
    monkeypatch.setenv("API_KEY", "abc")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    entry.main()
    assert run_calls == [{"host": "0.0.0.0", "port": 9000}]


def test_auth_on_without_key_refuses_to_start(run_calls: list[dict[str, Any]]) -> None:
    with pytest.raises(SystemExit, match="API_KEY is not set"):
        entry.main()
    assert run_calls == []
