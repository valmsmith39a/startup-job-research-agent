import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from job_research_mcp.server import build_app

TEST_API_KEY = "test-key-0123456789"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def _serve(api_key: str | None) -> Iterator[str]:
    """Run the real app under uvicorn on a free port."""
    port = _free_port()
    config = uvicorn.Config(build_app(api_key=api_key), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def server_url() -> Iterator[str]:
    """The app with auth on, requiring TEST_API_KEY."""
    yield from _serve(TEST_API_KEY)


@pytest.fixture(scope="session")
def open_server_url() -> Iterator[str]:
    """The app with auth disabled, as with AUTH_DISABLED=true."""
    yield from _serve(None)
