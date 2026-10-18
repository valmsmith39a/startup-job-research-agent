"""The FastAPI app factory and the unauthenticated health check."""

from fastapi import FastAPI

from job_research_api.auth import BearerAuthMiddleware


def create_app(*, api_key: str | None) -> FastAPI:
    """Build the app.

    `api_key` is required on every request except /health; None disables
    auth (local testing only, see `auth.api_key_from_env`).
    """
    app = FastAPI(title="job-research-api", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe. Unauthenticated by design."""
        return {"status": "ok"}

    if api_key is not None:
        app.add_middleware(BearerAuthMiddleware, api_key=api_key)
    return app
