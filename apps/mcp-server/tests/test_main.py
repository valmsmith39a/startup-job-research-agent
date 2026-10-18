"""Startup checks in `job_research_mcp.__main__.main`. uvicorn.run is stubbed; nothing binds."""

from typing import Any

import pytest

from job_research_mcp import __main__ as entry


@pytest.fixture
def run_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: calls.append(kwargs))
    for name in ("MCP_API_KEY", "AUTH_DISABLED", "HOST", "PORT"):
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
    monkeypatch.setenv("MCP_API_KEY", "abc")
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
    assert run_calls == [{"host": host or "127.0.0.1", "port": 8000}]


def test_auth_on_with_key_starts_on_any_host(monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, Any]]) -> None:
    monkeypatch.setenv("MCP_API_KEY", "abc")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    entry.main()
    assert run_calls == [{"host": "0.0.0.0", "port": 9000}]


def test_auth_on_without_key_refuses_to_start(run_calls: list[dict[str, Any]]) -> None:
    with pytest.raises(SystemExit, match="MCP_API_KEY is not set"):
        entry.main()
    assert run_calls == []
