.PHONY: install
install: ## Install the virtual environment and install the pre-commit hooks
	@echo "🚀 Creating virtual environment using uv"
	@uv sync
	@uv run pre-commit install

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo "🚀 Linting code: Running pre-commit"
	@uv run ruff format
	@uv run ruff check --fix
	@echo "🚀 Static type checking: Running ty"
	@uv run ty check ./src/text_mate_backend
	@varlock scan

.PHONY: env-load
env-load: ## Validate the .env file against the Configuration model
	@echo "🔍 Validating .env file"
	@pass-cli login
	./scripts/run-varlock.sh load

.PHONY: test
test: ## Test the code with pytest
	@echo "🚀 Testing code: Running pytest"
	@uv run python -m pytest --doctest-modules

.PHONY: docker-up
docker-up: ## Build and run the Docker container
	@echo "🐳 Running docker compose"
	@./scripts/run-varlock.sh run -- docker compose up -d

.PHONY: docker-down
docker-down: ## Stop and remove the Docker container
	@echo "🐳 Stopping docker compose"
	@./scripts/run-varlock.sh run -- docker compose down

.PHONY: docker-logs
docker-logs: ## Show docker compose logs
	@./scripts/run-varlock.sh run -- docker compose logs

.PHONY: run
run: ## Run the application
	@echo "🚀 Running the application"
	./scripts/run-varlock.sh run -- uv run fastapi run ./src/text_mate_backend/app.py --port 8000

.PHONY: dev
dev: ## Run the application in development mode
	@echo "🚀 Running the application in development mode"
	./scripts/run-varlock.sh run -- uv run fastapi dev ./src/text_mate_backend/app.py --port 8000

.PHONY: help
help:
	@uv run python -c "import re; \
	[[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
