"""
FastAPI application for ImageToSTLConverter backend
Refactored for cloud deployment with modular routes
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import download, health, image
from config.settings import get_cors_origins, settings
from services.stl_generator import initialize_color_mapping

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Initialize color mapping on startup
    """
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("Initializing color mapping reference matrices...")

    initialize_color_mapping(
        layer_count=settings.default_layer_count,
        layer_height=settings.default_layer_height
    )

    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


# Create FastAPI app with lifespan handler
app = FastAPI(
    title=settings.app_name,
    description="Backend API for converting images to color-separated STL files",
    version=settings.app_version,
    lifespan=lifespan,
    debug=settings.debug
)

# Configure CORS
cors_origins = get_cors_origins()
logger.info(f"CORS origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(image.router)
app.include_router(download.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower()
    )
