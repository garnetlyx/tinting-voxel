"""
FastAPI application for ImageToSTLConverter backend
Refactored for cloud deployment with modular routes
"""
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.rate_limiter import limiter
from api.routes import bug_report, batch, download, download_v2, filament, health, image, palette, param_search
from config.settings import get_cors_origins, settings
from services.analytics import analytics
from services.bug_report import install_bug_report_logging
from services.stl_generator import initialize_color_mapping

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
install_bug_report_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Initialize color mapping on startup and warm up matrix cache
    """
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("Environment: %s", settings.environment)
    logger.info("Initializing color mapping reference matrices...")

    initialize_color_mapping(
        layer_count=settings.default_layer_count,
        layer_height=settings.default_layer_height
    )

    # Warm up matrix cache for common preset configurations (layers 4 and 5)
    logger.info("Warming up matrix cache for preset configurations...")
    from services.matrix_cache import warmup_cache
    cache_entries = warmup_cache(layer_counts=[4, 5])
    # Warm the enumeration cost probe (absorbs cold-start numpy/BLAS init
    # before the first real request reads its rates).
    from services.stl_generator import _probe_throughput
    _probe_throughput()
    logger.info("Matrix cache warmed up with %d entries", cache_entries)

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
logger.info("CORS origins: %s", cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Analytics middleware
@app.middleware("http")
async def analytics_middleware(request: Request, call_next):
    """Track request metrics for usage analytics."""
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000

    # Only track /api/ routes (skip static files)
    path = request.url.path
    if path.startswith("/api/"):
        analytics.record_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
        )

    return response


# Analytics endpoint
@app.get("/api/analytics", tags=["Analytics"])
@limiter.limit("10/minute")
async def api_analytics(request: Request):
    """Get usage analytics summary."""
    return analytics.get_summary()


# Matrix cache stats endpoint
@app.get("/api/cache-stats", tags=["Analytics"])
@limiter.limit("10/minute")
async def api_cache_stats(request: Request):
    """Get matrix cache statistics."""
    from services.matrix_cache import get_cache_stats
    return get_cache_stats()


# Include routers
app.include_router(health.router)
app.include_router(bug_report.router)
app.include_router(image.router)
app.include_router(download.router)
app.include_router(download_v2.router)
app.include_router(filament.router)
app.include_router(batch.router)
app.include_router(palette.router)
app.include_router(param_search.router)

# Serve static frontend files in production (when ./static exists)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA index.html for non-API routes."""
        file_path = os.path.join(static_dir, full_path)
        # Resolve paths to prevent directory traversal attacks
        resolved_path = os.path.realpath(file_path)
        resolved_static = os.path.realpath(static_dir)
        # Ensure the resolved path is within static_dir
        if resolved_path != resolved_static and not resolved_path.startswith(resolved_static + os.sep):
            # Path traversal attempt - return index.html instead
            return FileResponse(os.path.join(static_dir, "index.html"))
        if os.path.isfile(resolved_path):
            return FileResponse(resolved_path)
        return FileResponse(os.path.join(static_dir, "index.html"))

    logger.info("Serving static frontend from %s", static_dir)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower()
    )
