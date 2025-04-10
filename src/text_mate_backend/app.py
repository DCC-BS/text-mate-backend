from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from text_mate_backend.container import Container

# Import routers
from text_mate_backend.routers import (
    advisor,
    quick_action,
    sentence_rewrite,
    text_correction,
    text_rewrite,
    word_synonym,
)
from text_mate_backend.utils.configuration import config
from text_mate_backend.utils.load_env import load_env
from text_mate_backend.utils.logger import get_logger, init_logger
from text_mate_backend.utils.middleware import add_logging_middleware


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    load_env()
    init_logger()

    app = FastAPI(
        title="Text Mate API",
        description="API for text correction, rewriting, and other text-related services",
        version="0.1.0",
    )

    logger = get_logger("app")
    logger.info("Starting Text Mate API application")
    logger.info(f"Running with configuration: {config}")

    # Set up dependency injection container
    logger.debug("Configuring dependency injection container")
    container = Container()
    container.wire(modules=[text_correction, text_rewrite, advisor, quick_action, word_synonym, sentence_rewrite])
    container.check_dependencies()
    logger.info("Dependency injection configured")

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
    logger.info("All routers registered")

    logger.info("API setup complete")
    return app


app = create_app()
