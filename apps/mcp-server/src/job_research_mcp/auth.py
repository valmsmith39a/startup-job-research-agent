"""Static bearer-token auth for the MCP endpoint.

Every HTTP request except the public paths (the health check) must carry
`Authorization: Bearer <MCP_API_KEY>`. Auth is on by default; `AUTH_DISABLED=true`
turns it off for local testing only.
"""

import hmac
import json
import logging
from collections.abc import Collection, Mapping

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

PUBLIC_PATHS = frozenset({"/health"})
_TRUTHY = {"1", "true", "yes", "on"}


class AuthConfigError(RuntimeError):
    """Auth is enabled but no API key is configured."""


def api_key_from_env(environ: Mapping[str, str]) -> str | None:
    """Return the required API key, or None when AUTH_DISABLED is set.

    Raises AuthConfigError when auth is on and MCP_API_KEY is missing or blank,
    so a misconfigured deploy fails at startup instead of running open.
    """
    if environ.get("AUTH_DISABLED", "").strip().lower() in _TRUTHY:
        return None
    api_key = environ.get("MCP_API_KEY", "").strip()
    if not api_key:
        raise AuthConfigError(
            "MCP_API_KEY is not set. Set it (e.g. `openssl rand -hex 32`), or set "
            "AUTH_DISABLED=true for local testing only."
        )
    return api_key


class BearerAuthMiddleware:
    """Pure ASGI middleware: 401 unless the bearer token matches. Lifespan and public paths pass through."""

    def __init__(self, app: ASGIApp, api_key: str, public_paths: Collection[str] = PUBLIC_PATHS) -> None:
        if not api_key:
            raise ValueError("api_key must be non-empty")
        self.app = app
        self._api_key = api_key.encode()
        self.public_paths = public_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.public_paths:
            await self.app(scope, receive, send)
            return
        scheme, _, token = dict(scope["headers"]).get(b"authorization", b"").partition(b" ")
        if scheme.lower() == b"bearer" and hmac.compare_digest(token.strip(), self._api_key):
            await self.app(scope, receive, send)
            return
        await _unauthorized(send)


async def _unauthorized(send: Send) -> None:
    body = json.dumps({"error": "unauthorized", "detail": "Missing or invalid bearer token."}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", b'Bearer realm="job-research-mcp"'),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
