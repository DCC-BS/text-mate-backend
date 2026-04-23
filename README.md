# Text Mate (Backend)

Text Mate Backend is a powerful Python FastAPI service that provides advanced text analysis and transformation capabilities powered by AI. This repository contains the backend services for the Text Mate application; the frontend is built with Nuxt.js and available at [https://github.com/DCC-BS/text-mate-frontend](https://github.com/DCC-BS/text-mate-frontend).

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/github/license/DCC-BS/text-mate-backend)](https://img.shields.io/github/license/DCC-BS/text-mate-backend)

---

<p align="center">
  <a href="https://dcc-bs.github.io/documentation/">DCC Documentation & Guidelines</a> | <a href="https://www.bs.ch/daten/databs/dcc">DCC Website</a>
</p>

---

## Features

### Core Capabilities
- **Text Rewriting**: Advanced text transformation with customizable parameters
- **Document Advisor**: Validates text against reference documents and style guides
- **Word Synonyms**: Intelligent synonym suggestions based on context
- **Sentence Rewrite**: Context-aware sentence transformation
- **Document Conversion**: Convert documents using Docling service (PDF, DOCX, etc.)

### Quick Actions
Many specialized AI-powered text transformations:
- **Summarize**: Generate concise summaries of long texts
- **Bullet Points**: Convert paragraphs into structured bullet points
- **Formality**: Adjust text formality level (formal/informal)
- **Medium Length**: Optimize text for medium-length output
- **Plain Language**: Simplify complex text to plain language
- **Social Media**: Optimize content for social media platforms
- **Proofread**: Comprehensive grammar and style checking
- **Character Speech**: Adapt text to character voice and speech patterns
- **Custom**: Flexible custom text transformations

### Development Features
- **Streaming Responses**: Real-time text generation with streaming support
- **Health Probes**: Built-in health check endpoints for all services
- **Logfire Integration**: Advanced debugging and monitoring in development mode
- **Azure AD Authentication**: Enterprise-ready authentication with Azure AD

## Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) with Python 3.13+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Dependency Injection**: Dependency-Injector
- **LLM Integration**: pydantic-ai for AI model integration
- **AI Model**: Qwen3 32B served via vLLM
- **Document Processing**: Docling
- **Containerization**: Docker and Docker Compose
- **Monitoring**: Logfire for observability

## Prerequisites

- **Python**: 3.13 or higher
- **uv package manager**: [Installation guide](https://github.com/astral-sh/uv)
- **Docker & Docker Compose**: For containerized deployment
- **NVIDIA GPU** with CUDA support:
  - Minimum 2 GPUs recommended (one for vLLM, one for Docling)
  - GPU memory: ~20GB for Qwen3-32B-AWQ model
  - CUDA toolkit installed
- **varlock**: For environment variables validation (optional but recommended)
- **pass-cli**: For varlock with Proton Pass integration

## Setup

### Environment Configuration

Create a `.env` file in the project root with the required environment variables:

```
AUTH_MODE=none # or azure
LOG_LEVEL=debug
HMAC_SECRET=... # create a new secret with openssl rand 32 | base64
```

#### Optional Environment Variables

The following environment variables have defaults and can be overridden as needed:

| Variable | Description | Default | Type |
|----------|-------------|---------|------|
| **Environment Settings** |
| `APP_MODE` | Application mode (controls varlock validation) | `dev` | enum: dev, ci, build, prod |
| `IS_PROD` | Flag for production mode (used by logger) | Auto-calculated from APP_MODE | boolean |
| **Ports** |
| `PORT` | FastAPI backend app port | `8000` | port |
| `LLM_API_PORT` | LLM API port | `8001` | port |
| `CLIENT_PORT` | Client application port | `3000` | port |
| `DOCLING_API_PORT` | Docling API port | `5001` | port |
| **URLs** |
| `CLIENT_URL` | Client application URL | `http://localhost:3000` (dev) | URL |
| `DOCLING_URL` | Docling service URL | `http://localhost:5001/v1` (dev) | URL |
| `LLM_URL` | LLM API URL | `http://localhost:8001/v1` (dev) | URL |
| `LLM_HEALTH_CHECK_URL` | LLM health check URL | `http://localhost:8001/health` (dev) | URL |
| **LLM Configuration** |
| `LLM_MODEL` | Model for LLM API | `Qwen/Qwen3-32B-AWQ` | string |
| `LLM_API_KEY` | API key for OpenAI authentication | `none` | string (sensitive in prod) |
| **Service Keys** |
| `DOCLING_API_KEY` | Docling API key | `none` | string (sensitive in prod) |
| `HUGGING_FACE_HUB_TOKEN` | Hugging Face API token | - | string (optional, sensitive) |
| **Docker Cache Directories** |
| `CACHE_DIR` | Base cache directory | `~/.cache` | path |
| `HUGGING_FACE_CACHE_DIR` | Hugging Face cache directory | `${CACHE_DIR}/huggingface` | path |

> **Note:** URLs are automatically set based on the `APP_MODE`. In production, these must be configured explicitly.

#### Azure Environment Variables

When `AUTH_MODE=azure`, the following Azure AD variables are **required**:

| Variable | Description | Default | Type |
|----------|-------------|---------|------|
| `AZURE_CLIENT_ID` | Azure AD application client ID | - | UUID (required) |
| `AZURE_TENANT_ID` | Azure AD tenant ID | - | UUID (required) |
| `AZURE_FRONTEND_CLIENT_ID` | Azure AD frontend application client ID | - | UUID (required) |
| `AZURE_SCOPE_DESCRIPTION` | Azure AD authentication scope | `user_impersonation` | string |

> **Note:** You can create a Hugging Face token [here](https://huggingface.co/settings/tokens).

Use [varlock](https://varlock.dev/) to validate the env variables:

```bash
varlock load
```

### Install Dependencies

Install dependencies and pre-commit hooks:

```bash
make install
```

Or manually:

```bash
uv sync
uv run pre-commit install
```

## Services Architecture

The application consists of four main services:

| Service | Port | Description |
|---------|------|-------------|
| **FastAPI Backend** | 8000 | Main application API |
| **vLLM Service** | 8001 | Qwen3-32B-AWQ model inference (v0.17.1) |
| **Docling** | 5001 | Document conversion service |

### GPU Allocation
- GPU 0 (`device_ids: ["0"]`): vLLM service for LLM inference
- GPU 1 (`device_ids: ["1"]`): Docling for document processing

## Development

### Start Development Server

```bash
# Start all required services with Docker
make docker-up

# Start the development server
make dev
```

The API will be available at `http://localhost:8000`

### API Documentation

Access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Development Tools

```bash
# Run code quality checks (format, lint, type check)
make check

# Run tests
make test

# Run tests with coverage
uv run pytest --cov=src/text_mate_backend tests/

# Run specific test file
uv run pytest tests/test_example.py
```

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies and pre-commit hooks |
| `make dev` | Start development server with hot reload |
| `make run` | Start production server |
| `make test` | Run test suite |
| `make check` | Run format, lint, type check, and varlock scan |
| `make docker-up` | Start all Docker services |
| `make docker-down` | Stop all Docker services |
| `make docker-logs` | View Docker service logs |
| `make help` | Show all available commands |

## Production

### Run Production Server

```bash
make run
```

Or manually:

```bash
FORCE_COLOR=1 varlock run -- uv run fastapi run ./src/text_mate_backend/app.py --port 8000
```

## Docker Deployment

### Using Pre-built Image

```bash
docker pull ghcr.io/dcc-bs/text-mate-backend:latest
```

### Manual Docker Build

```bash
# Build the Docker image
docker build -t text-mate-backend .

# Run the container
docker run -p 8000:8000 text-mate-backend
```

## Project Architecture

```
src/text_mate_backend/
├── app.py                          # FastAPI application entry point
├── container.py                    # Dependency injection container
├── agents/                         # AI agent implementations
│   └── agent_types/
│       ├── quick_actions/         # Quick action agents (8 types)
│       ├── advisor_agent.py       # Document advisor
│       ├── sentence_rewrite_agent.py
│       └── word_synonym_agent.py
├── models/                         # Pydantic data models and schemas
├── routers/                        # API endpoint definitions
│   ├── advisor.py                 # Document advisor endpoint
│   ├── convert_route.py           # Document conversion endpoint
│   ├── quick_action.py            # Quick actions endpoint
│   ├── sentence_rewrite.py        # Sentence rewrite endpoint
│   └── word_synonym.py            # Word synonym endpoint
├── services/                       # Business logic services
│   ├── actions/                   # Quick action service
│   └── document_conversion_service.py
└── utils/                          # Utility functions and helpers
    ├── auth.py                    # Authentication utilities
    ├── configuration.py           # Configuration management
    └── middleware.py              # Request/response middleware

text_mate_tools/                    # Utility scripts
├── preprocess_document_rules.py   # Document rule preprocessing
├── count_rules_per_file.py        # Rule counting utility
└── analyse_ruels.py               # Rule analysis utility

docs/                               # Reference documents and style guides
tests/                              # Unit and integration tests
```

## Troubleshooting

### GPU Memory Errors

**Issue**: Out of memory errors when starting vLLM service

**Solutions**:
- Ensure GPU has at least 20GB memory
- Reduce `--gpu-memory-utilization` in docker-compose.yml (default: 0.90)
- Reduce `--max-model-len` (default: 6000)

### Hugging Face Token Issues

**Issue**: Cannot download model from Hugging Face

**Solutions**:
- Verify `HUGGING_FACE_HUB_TOKEN` is set correctly
- Ensure token has read access to the model repository
- Create token at https://huggingface.co/settings/tokens

### Service Health Check Failures

**Issue**: Health check endpoint returns errors

**Solutions**:
- Check if all services are running: `docker ps`
- View service logs: `make docker-logs`
- Verify URLs in `.env` match Docker service names
- Check GPU availability: `nvidia-smi`

### Varlock Configuration Issues

**Issue**: varlock validation fails

**Solutions**:
- Ensure pass-cli is installed and authenticated
- Check Proton Pass credentials
- Verify `.env.schema` syntax
- Run `varlock load` for detailed errors

### Authentication Errors (Azure AD)

**Issue**: Azure AD authentication fails

**Solutions**:
- Verify all Azure environment variables are set
- Check `AZURE_CLIENT_ID` and `AZURE_TENANT_ID` are correct
- Ensure Azure AD app registration is configured properly
- Verify redirect URIs match your application URL

## License

[MIT](LICENSE) © Data Competence Center Basel-Stadt

<a href="https://www.bs.ch/schwerpunkte/daten/databs/schwerpunkte/datenwissenschaften-und-ki"><img src="./_imgs/databs_log.png" alt="DCC Logo" width="200" /></a>

Datenwissenschaften und KI <br>
Developed with ❤️ by DCC - Data Competence Center
