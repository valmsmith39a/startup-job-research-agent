"""Open roles from Ashby's public job board API, trimmed for a model to read.

Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
"""

from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"
BOARD_URL = "https://jobs.ashbyhq.com/{board}"
BOARD_HOST = "jobs.ashbyhq.com"
USER_AGENT = "startup-job-research-agent/0.1 (+https://github.com/valmsmith39a/startup-job-research-agent)"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

DESCRIPTION = """\
List a company's open job postings from its Ashby job board (jobs.ashbyhq.com).

Use this when the user asks about open roles, hiring, or specific jobs at a company \
that uses Ashby as its applicant tracking system, or gives a jobs.ashbyhq.com link. \
Pass the board name (the slug after jobs.ashbyhq.com/, often the company name, and \
case-sensitive) or the full jobs.ashbyhq.com URL.

Returns each listed job's title, department, team, locations, workplace type, \
employment type, published compensation (if any), publish date, and job and apply \
URLs, plus a source_url for the board. Job descriptions are not included.

If no Ashby board exists for the name, the company may use a different applicant \
tracking system (e.g. Greenhouse or Lever) or a different board slug; this tool \
cannot search for it.\
"""


class AshbyJob(BaseModel):
    title: str
    department: str | None = None
    team: str | None = None
    location: str | None = None
    secondary_locations: list[str] = Field(default_factory=list)
    workplace_type: str | None = Field(None, description="OnSite, Hybrid or Remote, as Ashby reports it.")
    is_remote: bool
    employment_type: str | None = Field(None, description="e.g. FullTime, PartTime, Intern, Contract.")
    compensation: str | None = Field(None, description="Published compensation summary; null if not published.")
    published_at: str | None = None
    job_url: str
    apply_url: str | None = None


class AshbyJobsResult(BaseModel):
    company: str = Field(description="The Ashby board name that was queried.")
    source_url: str = Field(description="Public job board page these jobs come from.")
    fetched_at: datetime
    total_listed_jobs: int = Field(description="Listed jobs on the board before keyword/remote filters.")
    total_jobs: int = Field(description="Jobs returned after filters.")
    jobs: list[AshbyJob]


def parse_board_name(company: str) -> str:
    """Return the board slug from a bare name or a jobs.ashbyhq.com URL. Case is preserved."""
    value = company.strip()
    if not value:
        raise ToolError("Provide an Ashby board name, e.g. 'openai', or a jobs.ashbyhq.com URL.")
    if "/" in value or value.lower().startswith(BOARD_HOST):
        parts = urlsplit(value if "://" in value else f"https://{value}")
        if parts.hostname != BOARD_HOST:
            raise ToolError(
                f"'{company}' is not a jobs.ashbyhq.com URL. Pass an Ashby board name or a "
                "https://jobs.ashbyhq.com/<board> link."
            )
        segments = [s for s in parts.path.split("/") if s]
        if not segments:
            raise ToolError(f"'{company}' has no board name after jobs.ashbyhq.com/.")
        value = segments[0]
    return unquote(value)


def _secondary_locations(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    names = (item.get("location") for item in raw if isinstance(item, dict))
    return [name for name in names if name]


def _compensation(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    return raw.get("compensationTierSummary") or raw.get("scrapeableCompensationSalarySummary") or None


def trim_job(raw: dict[str, Any]) -> AshbyJob:
    """Keep only what a model needs; descriptions and nested compensation tiers are dropped."""
    workplace_type = raw.get("workplaceType")
    return AshbyJob(
        title=raw.get("title") or "Untitled",
        department=raw.get("department") or None,
        team=raw.get("team") or None,
        location=raw.get("location") or None,
        secondary_locations=_secondary_locations(raw.get("secondaryLocations")),
        workplace_type=workplace_type,
        is_remote=bool(raw.get("isRemote")) or workplace_type == "Remote",
        employment_type=raw.get("employmentType"),
        compensation=_compensation(raw.get("compensation")),
        published_at=raw.get("publishedAt"),
        job_url=raw["jobUrl"],
        apply_url=raw.get("applyUrl"),
    )


async def _fetch_board(board: str) -> dict[str, Any]:
    url = API_URL.format(board=quote(board, safe=""))
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url, params={"includeCompensation": "true"})
    except httpx.TimeoutException:
        raise ToolError(f"Ashby did not respond in time for board '{board}'. Try again shortly.") from None
    except httpx.TransportError as exc:
        raise ToolError(f"Could not reach Ashby for board '{board}' ({type(exc).__name__}). Try again shortly.") from None

    if response.status_code == 404:
        raise ToolError(
            f"No Ashby job board named '{board}'. Board names are case-sensitive: check the slug in "
            f"https://jobs.ashbyhq.com/<board>. The company may also use a different applicant tracking system."
        )
    if response.status_code >= 500:
        raise ToolError(f"Ashby returned a server error ({response.status_code}) for board '{board}'. Try again shortly.")
    if response.status_code != 200:
        raise ToolError(f"Ashby returned HTTP {response.status_code} for board '{board}'.")
    try:
        data = response.json()
    except ValueError:
        raise ToolError(f"Ashby returned a response for board '{board}' that was not valid JSON.") from None
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise ToolError(f"Ashby returned an unexpected response shape for board '{board}'.")
    return data


async def get_ashby_jobs(
    company: Annotated[
        str,
        Field(description="Ashby board name (the slug in jobs.ashbyhq.com/<board>, case-sensitive) or a full jobs.ashbyhq.com URL."),
    ],
    keyword: Annotated[
        str | None,
        Field(description="Optional case-insensitive filter on job title, e.g. 'engineer'."),
    ] = None,
    remote_only: Annotated[bool, Field(description="If true, return only remote jobs.")] = False,
) -> AshbyJobsResult:
    board = parse_board_name(company)
    data = await _fetch_board(board)

    listed = [
        trim_job(raw)
        for raw in data["jobs"]
        if isinstance(raw, dict) and raw.get("isListed", True) and raw.get("jobUrl")
    ]
    jobs = listed
    if keyword and keyword.strip():
        needle = keyword.strip().casefold()
        jobs = [job for job in jobs if needle in job.title.casefold()]
    if remote_only:
        jobs = [job for job in jobs if job.is_remote]

    return AshbyJobsResult(
        company=board,
        source_url=BOARD_URL.format(board=quote(board, safe="")),
        fetched_at=datetime.now(UTC),
        total_listed_jobs=len(listed),
        total_jobs=len(jobs),
        jobs=jobs,
    )
