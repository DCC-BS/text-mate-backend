# Stage 1: Builder
FROM python:3.14-alpine AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_HTTP_TIMEOUT=120

WORKDIR /app

RUN apk add --no-cache build-base git protoc protobuf-dev rust cargo

COPY pyproject.toml uv.lock ./

# Install dependencies
# --locked: Sync with lockfile
# --no-dev: Exclude development dependencies
# --no-install-project: Install dependencies only (caching layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY . /app

# Sync project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Stage 2: Runtime
FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user (Alpine syntax)
RUN addgroup -S app && adduser -S app -G app

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app --chmod=755 run.sh /app/run.sh

# Enable virtual environment
ENV PATH="/app/.venv/bin:$PATH"

USER app

ENV ENVIRONMENT=production

ENTRYPOINT ["/app/run.sh"]
