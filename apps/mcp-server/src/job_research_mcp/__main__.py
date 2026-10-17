"""Entry point: `uv run job-research-mcp` or `python -m job_research_mcp`."""

import logging
import os
import sys

import uvicorn

from job_research_mcp.auth import AuthConfigError, api_key_from_env
from job_research_mcp.server import build_app

logger = logging.getLogger("job_research_mcp")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    try:
        api_key = api_key_from_env(os.environ)
    except AuthConfigError as exc:
        sys.exit(f"Refusing to start: {exc}")
    if api_key is None:
        logger.warning("AUTH_DISABLED=true: the MCP endpoint accepts unauthenticated requests. Local testing only.")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(build_app(api_key=api_key, host=host), host=host, port=port)


if __name__ == "__main__":
    main()
