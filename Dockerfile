FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libssl-dev \
    libcurl4-gnutls-dev \
    curl \
    ca-certificates \
    && apt-get clean

WORKDIR /app

# install certificate
COPY ./ZID_BS_RootCA.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates


COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --frozen --no-install-project

COPY . /app

RUN chmod +x /app/entrypoint.sh

RUN uv sync --frozen

ENV ENVIRONMENT=production

ENTRYPOINT ["/app/entrypoint.sh"]
