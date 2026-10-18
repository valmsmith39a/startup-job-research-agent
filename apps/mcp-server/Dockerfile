# syntax=docker/dockerfile:1

# uv is copied from its official image; override UV_IMAGE to use a mirror.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.32
FROM ${UV_IMAGE} AS uv

# --- Build: resolve the locked dependencies into /app/.venv ---
FROM python:3.13-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# --- Runtime: just Python and the virtualenv, as a non-root user ---
FROM python:3.13-slim
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000
USER app
EXPOSE 8000
CMD ["job-research-mcp"]
