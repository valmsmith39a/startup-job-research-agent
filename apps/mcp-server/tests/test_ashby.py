"""get_ashby_jobs against a fixture of Ashby's documented response shape. No live calls."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from job_research_mcp.server import mcp
from job_research_mcp.tools.ashby import USER_AGENT, parse_board_name

BOARD = "examplco"
API = f"https://api.ashbyhq.com/posting-api/job-board/{BOARD}"
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ashby_board.json").read_text())


async def call(args: dict[str, Any]) -> tuple[bool, dict[str, Any] | None, str]:
    async with Client(mcp) as client:
        result = await client.call_tool("get_ashby_jobs", args)
    text = " ".join(getattr(block, "text", "") for block in result.content)
    return result.is_error, result.structured_content, text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("examplco", "examplco"),
        ("  ExamplCo  ", "ExamplCo"),
        ("https://jobs.ashbyhq.com/ExamplCo", "ExamplCo"),
        ("https://jobs.ashbyhq.com/examplco/1f6c1b5e-0000/application?utm=x#top", "examplco"),
        ("jobs.ashbyhq.com/examplco/", "examplco"),
        ("https://jobs.ashbyhq.com/Mistral%20AI", "Mistral AI"),
    ],
)
def test_parse_board_name(value: str, expected: str) -> None:
    assert parse_board_name(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "https://boards.greenhouse.io/examplco", "https://jobs.ashbyhq.com/"])
def test_parse_board_name_rejects(value: str) -> None:
    with pytest.raises(ToolError):
        parse_board_name(value)


@respx.mock
async def test_success_trims_and_drops_unlisted() -> None:
    route = respx.get(API).mock(return_value=httpx.Response(200, json=FIXTURE))

    is_error, data, _ = await call({"company": f"https://jobs.ashbyhq.com/{BOARD}"})

    assert not is_error and data is not None
    request = route.calls.last.request
    assert request.url.params["includeCompensation"] == "true"
    assert request.headers["User-Agent"] == USER_AGENT

    assert data["company"] == BOARD
    assert data["source_url"] == f"https://jobs.ashbyhq.com/{BOARD}"
    assert data["fetched_at"]
    assert data["total_listed_jobs"] == 3
    assert data["total_jobs"] == 3
    assert [job["title"] for job in data["jobs"]] == [
        "Senior Software Engineer, Platform",
        "Machine Learning Engineer",
        "Account Executive",
    ]

    first = data["jobs"][0]
    assert first == {
        "title": "Senior Software Engineer, Platform",
        "department": "Engineering",
        "team": "Platform",
        "location": "San Francisco, CA",
        "secondary_locations": ["New York, NY"],
        "workplace_type": "Hybrid",
        "is_remote": False,
        "employment_type": "FullTime",
        "compensation": "$180K – $240K • Offers Equity",
        "published_at": "2026-09-30T16:21:55.393+00:00",
        "job_url": "https://jobs.ashbyhq.com/examplco/1f6c1b5e-0000-4000-8000-000000000001",
        "apply_url": "https://jobs.ashbyhq.com/examplco/1f6c1b5e-0000-4000-8000-000000000001/application",
    }
    assert data["jobs"][1]["compensation"] is None
    assert data["jobs"][2]["compensation"] == "£90K - £110K"
    assert data["jobs"][2]["team"] is None

    dumped = json.dumps(data)
    assert "DESCRIPTION" not in dumped and "HIDDEN" not in dumped and "compensationTiers" not in dumped


@respx.mock
async def test_keyword_filter_is_case_insensitive() -> None:
    respx.get(API).mock(return_value=httpx.Response(200, json=FIXTURE))

    _, data, _ = await call({"company": BOARD, "keyword": "  ENGINEER "})

    assert data is not None
    assert [job["title"] for job in data["jobs"]] == ["Senior Software Engineer, Platform", "Machine Learning Engineer"]
    assert data["total_jobs"] == 2
    assert data["total_listed_jobs"] == 3


@respx.mock
async def test_remote_only_filter() -> None:
    respx.get(API).mock(return_value=httpx.Response(200, json=FIXTURE))

    _, data, _ = await call({"company": BOARD, "remote_only": True})

    assert data is not None
    assert [job["title"] for job in data["jobs"]] == ["Machine Learning Engineer"]
    assert data["jobs"][0]["is_remote"] is True


@respx.mock
async def test_404_says_no_board() -> None:
    respx.get("https://api.ashbyhq.com/posting-api/job-board/nope").mock(return_value=httpx.Response(404))

    is_error, _, text = await call({"company": "nope"})

    assert is_error
    assert "No Ashby job board named 'nope'" in text
    assert "case-sensitive" in text


@respx.mock
async def test_timeout_is_a_clear_error() -> None:
    respx.get(API).mock(side_effect=httpx.ReadTimeout("timed out"))

    is_error, _, text = await call({"company": BOARD})

    assert is_error
    assert "did not respond in time" in text


@respx.mock
async def test_5xx_is_a_clear_error() -> None:
    respx.get(API).mock(return_value=httpx.Response(503))

    is_error, _, text = await call({"company": BOARD})

    assert is_error
    assert "server error (503)" in text


async def test_non_ashby_url_is_rejected_without_a_request() -> None:
    with respx.mock(assert_all_called=False) as router:
        is_error, _, text = await call({"company": "https://boards.greenhouse.io/examplco"})
    assert is_error
    assert "not a jobs.ashbyhq.com URL" in text
    assert not router.calls
