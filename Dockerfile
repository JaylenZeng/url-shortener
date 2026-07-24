# syntax=docker/dockerfile:1

# ---- build stage ----
FROM python:3.13-slim AS builder

# uv: fast dependency install
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# cache deps separately from source
COPY server/pyproject.toml server/uv.lock ./

# install into a self-contained venv at /app/.venv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY server/ .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- runtime stage ----
FROM python:3.13-slim AS runtime

# non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# copy venv + source from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# web process. worker overrides CMD in compose.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:8000"]
