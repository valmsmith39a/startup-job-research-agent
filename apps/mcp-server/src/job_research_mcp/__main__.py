"""Entry point: `uv run job-research-mcp` or `python -m job_research_mcp`."""

import logging
import os
import sys

import uvicorn

from job_research_mcp.auth import AuthConfigError, api_key_from_env
from job_research_mcp.server import build_app

logger = logging.getLogger("job_research_mcp")

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    try:
        api_key = api_key_from_env(os.environ)
    except AuthConfigError as exc:
        sys.exit(f"Refusing to start: {exc}")
    if api_key is None:
        if host not in LOOPBACK_HOSTS:
            sys.exit(
                f"Refusing to start: AUTH_DISABLED=true is only allowed on a loopback HOST "
                f"(127.0.0.1, localhost, ::1), not {host!r}. Unset AUTH_DISABLED and set MCP_API_KEY."
            )
        logger.warning("AUTH_DISABLED=true: the MCP endpoint accepts unauthenticated requests. Local testing only.")

    uvicorn.run(build_app(api_key=api_key, host=host), host=host, port=port)


if __name__ == "__main__":
    main()
