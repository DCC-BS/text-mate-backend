from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import logfire
from dcc_backend_common.fastapi_error_handling import inject_api_error_handler
from dcc_backend_common.fastapi_health_probes import health_probe_router
from dcc_backend_common.fastapi_health_probes.router import ServiceDependency
from dcc_backend_common.logger import get_logger, init_logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog.stdlib import BoundLogger

from text_mate_backend.container import Container

# Import routers
from text_mate_backend.routers import (
    advisor,
    convert_route,
    quick_action,
    sentence_rewrite,
    text_correction,
    word_synonym,
)
from text_mate_backend.utils.middleware import add_logging_middleware

logfire.configure()
logfire.instrument_pydantic_ai()


def create_app() -> FastAPI:
    init_logger()

    logger: BoundLogger = get_logger("app")
    logger.info("Starting Text Mate API application")

    # Set up dependency injection container
    logger.debug("Configuring dependency injection container")
    container = Container()
    container.wire(modules=[text_correction, advisor, quick_action, word_synonym, sentence_rewrite, convert_route])
    container.check_dependencies()
    logger.info("Dependency injection configured")

    config = container.config()
    logger.info(f"Running with configuration: {config}")

    service_dependencies: list[ServiceDependency] = [
        {"name": "llm", "health_check_url": config.llm_health_check_url, "api_key": config.llm_api_key},
        {
            "name": "language tool",
            "health_check_url": config.language_tool_api_health_check_url,
            "api_key": None,
        },
    ]

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        """
        Load OpenID configuration on application startup and yield control for the application's runtime.

        This lifecycle context ensures the OpenID discovery/configuration is loaded before the application begins
        serving requests.
        """
        if not config.disable_auth:
            await container.azure_service().load_config()
        yield

    app = FastAPI(
        title="Text Mate API",
        description="API for text correction, rewriting, and other text-related services",
        version="0.1.0",
        swagger_ui_oauth2_redirect_url="/oauth2-redirect",
        swagger_ui_init_oauth={
            "usePkceWithAuthorizationCodeGrant": True,
            "clientId": config.azure_frontend_client_id,
        },
        lifespan=lifespan,
    )

    app.include_router(health_probe_router(service_dependencies))
    inject_api_error_handler(app)

    # Configure CORS
    logger.debug("Setting up CORS middleware")
    app.add_middleware(
        CORSMiddleware,  # ty:ignore[invalid-argument-type]
        allow_origins=[config.client_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS configured with origin: {config.client_url}")

    # Add logging middleware
    add_logging_middleware(app)

    # Include routers
    logger.debug("Registering API routers")
    app.include_router(text_correction.create_router())
    app.include_router(advisor.create_router())
    app.include_router(quick_action.create_router())
    app.include_router(word_synonym.create_router())
    app.include_router(sentence_rewrite.create_router())
    app.include_router(convert_route.create_router())
    logger.info("All routers registered")

    logger.info("API setup complete")
    return app


app = create_app()
