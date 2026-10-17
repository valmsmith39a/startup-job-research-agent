"""Entry point: `uv run job-research-mcp` or `python -m job_research_mcp`."""

import os

import uvicorn

from job_research_mcp.server import build_app


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(build_app(host=host), host=host, port=port)


if __name__ == "__main__":
    main()
