# Text Mate (Backend)

Text Mate Backend is a powerful Python FastAPI service that provides advanced text analysis, correction, and transformation capabilities. This repository contains the backend services for the Text Mate application; the frontend is built with Nuxt.js and available at [https://github.com/DCC-BS/text-mate-frontend](https://github.com/DCC-BS/text-mate-frontend).

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/github/license/DCC-BS/transcribo-backend)](https://img.shields.io/github/license/DCC-BS/transcribo-backend)

---

<p align="center">
  <a href="https://dcc-bs.github.io/documentation/">DCC Documentation & Guidelines</a> | <a href="https://www.bs.ch/daten/databs/dcc">DCC Website</a>
</p>

---

## Features

- **Text Correction**: Grammar and spelling correction using LanguageTool integration
- **Text Rewriting**: Advanced text transformation with customizable parameters
- **Document Advisor**: Validates text against reference documents
- **Quick Actions**: Various text processing utilities
- **Word Synonyms**: Intelligent synonym suggestions
- **Sentence Rewrite**: Context-aware sentence transformation

## Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) with Python 3.13
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Dependency Injection**: Dependency-Injector
- **LLM Integration**: LlamaIndex for LLM model integration
- **Containerization**: Docker and Docker Compose
- **AI Models**: vLLM for serving Qwen3 32B model

## Setup

### Prerequisites

- Python 3.13+
- uv package manager
- Docker and Docker Compose (for containerized deployment)
- NVIDIA GPU with CUDA support (for LLM services)

### Environment Configuration

Create a `.env` file in the project root with the required environment variables:

```
AUTH_MODE=none # or azure
LOG_LEVEL=debug
HMAC_SECRET=... # create a new secret with openssl rand 32 | base64

IS_PROD=false # this will be calculated from the ENVIRONMENT when varlock is used else this needs to be set for the logger

# optional else defaults will be used
# ---

ENVIRONMENT=development # defaults to development when varlock is used else production

## Ports

# The port of the fastapi backend app
PORT=8000
LLM_API_PORT=8001
CLIENT_PORT=3000
DOCLING_API_PORT=5001
LANGUAGE_TOOL_PORT=8010

## Urls

# The URL for client application
CLIENT_URL=http://localhost:${CLIENT_PORT}

# The URL for Language Tool API
LANGUAGE_TOOL_API_URL=http://localhost:${LANGUAGE_TOOL_PORT}/v2

# The URL for Docling service
DOCLING_URL=http://localhost:${DOCLING_API_PORT}/v1

# The URL for LLM API
LLM_URL=http://localhost:${LLM_API_PORT}

# The URL for LLM health check API
LLM_HEALTH_CHECK_URL=${LLM_URL}/health

## LLM

# The model for LLM API
LLM_MODEL='Qwen/Qwen3-32B-AWQ'

# The API key for authenticating with OpenAI
LLM_API_KEY=none

# For the docker compose also set these variables
# ---
HUGGING_FACE_HUB_TOKEN=your_huggingface_token

## Caching dirs for docker
CACHE_DIR="~/.cache"
LANGUAGE_TOOL_CACHE_DIR=${CACHE_DIR}/languagetool
HUGGING_FACE_CACHE_DIR=${CACHE_DIR}/huggingface
```
> **Note:** The `HUGGING_FACE_HUB_TOKEN` is required for Hugging Face API access. You can create a token [here](https://huggingface.co/settings/tokens).

Use [varlock](https://varlock.dev/) to validate the env variables:

```bash
varlock load
```

### Install Dependencies

Install dependencies using uv:

```bash
uv sync
```

## Development

Start the development server:

```bash
uv run fastapi dev ./src/text_mate_backend/app.py
```

## Production

Run the production server:

```bash
uv run fastapi run ./src/text_mate_backend/app.py
```

## Docker Deployment

The application includes a Dockerfile and Docker Compose configuration for easy deployment:

### Using Docker Compose

```bash
# Start all services with Docker Compose
docker compose up -d

# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f
```

### Using Dockerfile Only

```bash
# Build the Docker image
docker build -t text-mate-backend .

# Run the container
docker run -p 8000:8000 text-mate-backend
```

## Testing & Development Tools

Run tests with pytest:

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/text_mate_backend tests/
```

Code formatting and linting:

```bash
# Format code with ruff
uv run ruff format .

# Run linting
uv run ruff check .

# Run type checking
uv run mypy .
```

## Project Architecture

- `src/text_mate_backend/`: Main application code
  - `app.py`: FastAPI application entry point
  - `container.py`: Dependency injection container
  - `customLLMs/`: Custom LLM implementations
  - `models/`: Data models and schemas
  - `routers/`: API endpoint definitions
  - `services/`: Business logic services
  - `utils/`: Utility functions and helpers
- `docker/`: Docker configurations for services like LanguageTool
- `docs/`: Reference documents and documentation
- `tests/`: Unit and integration tests

## License

[MIT](LICENSE) © Data Competence Center Basel-Stadt

<a href="https://www.bs.ch/schwerpunkte/daten/databs/schwerpunkte/datenwissenschaften-und-ki"><img src="./_imgs/databs_log.png" alt="DCC Logo" width="200" /></a>

Datenwissenschaften und KI <br>
Developed with ❤️ by DCC - Data Competence Center
