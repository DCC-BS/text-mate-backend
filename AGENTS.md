# Agentic Coding Guidelines for text-mate-backend

## Essential Commands

**Development:**
```bash
make install        # Install dependencies and pre-commit hooks
make dev            # Start dev server on port 8000
make run            # Start production server
```

**Code Quality:**
```bash
make check          # Run all checks: lock file, format, lint, type check
uv run ruff format .           # Format code
uv run ruff check --fix .      # Fix linting issues
uv run ty check ./src/text_mate_backend  # Type checking
```

**Testing:**
```bash
make test           # Run all tests
uv run pytest tests/test_file.py::TestClass::test_method  # Run single test
uv run pytest -k test_name          # Run tests matching name
uv run pytest --cov=src/text_mate_backend tests/  # With coverage
```

**Building:**
```bash
make build          # Build wheel file
make env-example    # Generate .env.example from Configuration
```

## Code Style Guidelines

### Formatting
Line length: 120 chars, indent: 4 spaces (no tabs), double quotes, final newline, trim trailing whitespace

### Imports
Order: standard library, third-party, first-party. Combine as-imports.

### Docstrings
Use Google-style docstrings with Args, Returns, Raises sections.

### Type Hints
Python 3.13+ target, use type hints extensively with Annotated for descriptions.

### Naming Conventions
- Classes: PascalCase (`LanguageToolService`, `CorrectionResult`)
- Functions/methods: snake_case (`check_text`, `create_router`)
- Variables: snake_case (`text_preview`, `api_url`)
- Constants: SCREAMING_SNAKE_CASE
- Private methods: `_internal_method()`

### Error Handling
Use `@safe` decorator for automatic error handling, Result types for service methods:
```python
from returns.result import ResultE, Success, Failure, safe
from returns.pipeline import is_successful

@safe
def check_text(self, language: str, text: str) -> LanguageToolResponse:
    response = requests.post(url, data=data)
    response.raise_for_status()
    return LanguageToolResponse(**response.json())

result: ResultE[CorrectionResult] = service.correct_text(text, options)
if is_successful(result):
    correction_result = result.unwrap()
```

Custom exceptions with exception chaining:
```python
raise ApiErrorException({"status": 500, "errorId": ERROR_CODE, "debugMessage": str(e)}) from e
```

Guard clauses and early returns for better readability

### Dependency Injection
All dependencies managed through `Container`:
```python
from dependency_injector.wiring import inject, Provide
from text_mate_backend.container import Container

@inject
def create_router(service: MyService = Provide[Container.my_service]) -> APIRouter:
    pass
```

### Configuration
Use `get_env_or_throw()` for required env vars, `os.getenv()` with defaults for optional.

### Logging
Structured logging with key-value pairs, not string interpolation:
```python
from dcc_backend_common.logger import get_logger
logger = get_logger("module_name")
logger.info("User authenticated", user_id=user.id, method="oauth")
```

Levels: DEBUG (diagnostic), INFO (operational), WARNING (unexpected), ERROR (errors), CRITICAL (system-wide failures)

### Testing
Use descriptive test names following `test_<function>_<scenario>_<expected_result>`:
```python
import pytest
from pytest_mock import MockerFixture

@pytest.fixture
def mock_service(mocker: MockerFixture) -> MyService:
    return mocker.Mock(spec=MyService)

class TestMyClass:
    def test_correct_text_with_valid_input_returns_success(self, mock_service: MyService) -> None:
        mock_service.method.return_value = Success(result)
        assert is_successful(service.process())
```

### Data Structures
- **Pydantic BaseModel**: API input/output, configuration, external data with validation
- **dataclass**: Internal data containers, no validation needed (use frozen/slots)
- **TypedDict**: Dict-like data with type hints (JSON responses from external APIs)

### Async/Await Patterns
- Use `async def` for I/O-bound operations (HTTP calls, database queries)
- Use regular `def` for CPU-bound operations
- Use `httpx.AsyncClient` for async HTTP, reuse client instances
- Use `asyncio.gather()` for concurrent operations

### Functions vs Classes
Prefer functions over classes for stateless operations. Use dataclasses with frozen=True, slots=True, kw_only=True for data containers.

### Protocol vs ABC
Use `Protocol` for structural subtyping (duck typing with type safety). Use `ABC` when shared implementation or enforced inheritance needed.

### Modern Python Best Practices
- Use list comprehensions
- Use `pathlib` over `os.path`
- Use `enumerate` and `zip`
- Use f-strings for string formatting
- Use `is` or `is not` for None comparison

### Constants & Enums
Place shared constants in `utils/constants.py`, use StrEnum for string constants.

### File Structure
```
src/text_mate_backend/
├── app.py              # FastAPI app creation
├── container.py        # Dependency injection
├── agents/            # AI agent implementations
├── models/            # Pydantic models
├── routers/           # API endpoints
├── services/          # Business logic
└── utils/             # Helpers, auth, config, constants, decorators, context_managers
```

### API Design
Request/Response naming: `CreateUserRequest`, `UserResponse`, `UpdateUserRequest`
HTTP status codes: POST (201), GET (200), PATCH/PUT (200), DELETE (204)

### Versioning
Use Semantic Versioning: `MAJOR.MINOR.PATCH` (e.g., `2.1.0`)
- MAJOR: Breaking changes
- MINOR: New features (backwards-compatible)
- PATCH: Bug fixes (backwards-compatible)
