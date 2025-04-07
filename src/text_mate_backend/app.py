from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from text_mate_backend.container import Container

# Import routers
from text_mate_backend.routers import advisor, quick_action, text_correction, text_rewrite
from text_mate_backend.utils.configuration import config
from text_mate_backend.utils.load_env import load_env
from text_mate_backend.utils.logger import get_logger, init_logger


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    load_env()
    init_logger()

    app = FastAPI()
    logger = get_logger()

    logger.info(f"Running with configuration: {config}")

    container = Container()
    container.wire(modules=[text_correction, text_rewrite, advisor, quick_action])
    container.check_dependencies()

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.client_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(text_correction.create_router())
    app.include_router(text_rewrite.create_router())
    app.include_router(advisor.create_router())
    app.include_router(quick_action.create_router())

    return app


app = create_app()
