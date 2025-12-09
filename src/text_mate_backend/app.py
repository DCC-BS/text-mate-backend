from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from backend_common.fastapi_health_probes import health_probe_router
from backend_common.fastapi_health_probes.router import ServiceDependency
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from structlog.stdlib import BoundLogger

from text_mate_backend.container import Container

# Import routers
from text_mate_backend.models.error_codes import UNEXPECTED_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.routers import (
    advisor,
    convert_route,
    quick_action,
    sentence_rewrite,
    text_correction,
    text_rewrite,
    word_synonym,
)
from text_mate_backend.utils.load_env import load_env
from text_mate_backend.utils.logger import get_logger, init_logger
from text_mate_backend.utils.middleware import add_logging_middleware


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    load_env()
    init_logger()

    logger: BoundLogger = get_logger("app")
    logger.info("Starting Text Mate API application")

    # Set up dependency injection container
    logger.debug("Configuring dependency injection container")
    container = Container()
    container.wire(
        modules=[text_correction, text_rewrite, advisor, quick_action, word_synonym, sentence_rewrite, convert_route]
    )
    container.check_dependencies()
    logger.info("Dependency injection configured")

    config = container.config()
    logger.info(f"Running with configuration: {config}")

    service_dependencies: list[ServiceDependency] = [
        {"name": "llm", "health_check_url": config.llm_health_check_url, "api_key": config.openai_api_key},
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
        
        This lifecycle context ensures the OpenID discovery/configuration is loaded before the application begins serving requests. No teardown actions are performed.
        """
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

    def api_error_handler(request: Request, exc: Exception) -> Response:
        """
        Convert exceptions raised during request handling into a JSON HTTP response.
        
        If `exc` is an `ApiErrorException`, returns its `error_response` payload and status code.
        Otherwise returns a 500 response with `errorId` set to `UNEXPECTED_ERROR`, `status` 500, and a `debugMessage` containing the exception string.
        
        Parameters:
            request (Request): The incoming HTTP request that triggered the exception.
            exc (Exception): The exception raised during request processing.
        
        Returns:
            Response: A JSON HTTP response describing the error.
        """
        if isinstance(exc, ApiErrorException):
            return JSONResponse(
                status_code=exc.error_response["status"],
                media_type="application/json",
                content=exc.error_response,
            )

        return JSONResponse(
            status_code=500,
            media_type="application/json",
            content={"errorId": UNEXPECTED_ERROR, "status": 500, "debugMessage": str(exc)},
        )

    app.add_exception_handler(ApiErrorException, api_error_handler)

    # Configure CORS
    logger.debug("Setting up CORS middleware")
    app.add_middleware(
        CORSMiddleware,
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
    app.include_router(text_rewrite.create_router())
    app.include_router(advisor.create_router())
    app.include_router(quick_action.create_router())
    app.include_router(word_synonym.create_router())
    app.include_router(sentence_rewrite.create_router())
    app.include_router(convert_route.create_router())
    logger.info("All routers registered")

    logger.info("API setup complete")
    return app


app = create_app()