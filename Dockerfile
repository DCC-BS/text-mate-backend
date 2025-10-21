FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libssl-dev \
    libcurl4-gnutls-dev \
    curl \
    build-essential \
    && apt-get clean

WORKDIR /app

COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --frozen --no-install-project

COPY . /app

RUN chmod +x /app/entrypoint.sh

RUN uv sync --frozen

ENV ENVIRONMENT=production

ENTRYPOINT ["/app/entrypoint.sh"]
