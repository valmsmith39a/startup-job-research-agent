"""Static bearer-token auth for apps/api.

Every HTTP request except the public paths (the health check) must carry
`Authorization: Bearer <API_KEY>`. Auth is on by default; `AUTH_DISABLED=true`
turns it off for local testing only.

Copied from apps/mcp-server (`job_research_mcp.auth`, as of PR #5) with the env
var renamed; keep the two in step. See docs/DECISIONS.md for why it isn't shared.
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

    Raises AuthConfigError when auth is on and API_KEY is missing or blank,
    so a misconfigured deploy fails at startup instead of running open.
    """
    if environ.get("AUTH_DISABLED", "").strip().lower() in _TRUTHY:
        return None
    api_key = environ.get("API_KEY", "").strip()
    if not api_key:
        raise AuthConfigError(
            "API_KEY is not set. Set it (e.g. `openssl rand -hex 32`), or set "
            "AUTH_DISABLED=true for local testing only."
        )
    return api_key


class BearerAuthMiddleware:
    """Pure ASGI middleware: reject unless the bearer token matches.

    Only lifespan events and HTTP requests to public paths pass through unchecked.
    Every other scope (HTTP, and websocket should one ever be routed) needs the token;
    a rejected websocket is closed before accept, since it can't carry an HTTP 401.
    """

    def __init__(self, app: ASGIApp, api_key: str, public_paths: Collection[str] = PUBLIC_PATHS) -> None:
        if not api_key:
            raise ValueError("api_key must be non-empty")
        self.app = app
        self._api_key = api_key.encode()
        self.public_paths = public_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan" or (scope["type"] == "http" and scope["path"] in self.public_paths):
            await self.app(scope, receive, send)
            return
        scheme, _, token = dict(scope.get("headers", [])).get(b"authorization", b"").partition(b" ")
        if scheme.lower() == b"bearer" and hmac.compare_digest(token.strip(), self._api_key):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})  # 1008 = policy violation; servers answer 403
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
                (b"www-authenticate", b'Bearer realm="job-research-api"'),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
