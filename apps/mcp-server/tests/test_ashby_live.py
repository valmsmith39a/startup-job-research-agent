"""Optional smoke test against the real Ashby API. Skipped unless RUN_LIVE_TESTS=1.

    RUN_LIVE_TESTS=1 uv run pytest -m live
    RUN_LIVE_TESTS=1 ASHBY_LIVE_BOARD=<board> uv run pytest -m live
"""

import os

import pytest

from job_research_mcp.tools.ashby import get_ashby_jobs

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to hit the real Ashby API"),
]


async def test_real_board_returns_trimmed_jobs() -> None:
    board = os.environ.get("ASHBY_LIVE_BOARD", "ashby")
    result = await get_ashby_jobs(board)
    assert result.company == board
    assert result.total_jobs == len(result.jobs)
    for job in result.jobs:
        assert job.job_url.startswith("https://jobs.ashbyhq.com/")
