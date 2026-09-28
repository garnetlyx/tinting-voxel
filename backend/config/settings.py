"""
Application settings and environment configuration
Supports both development and production (cloud) environments
"""
import os

from pydantic import ConfigDict, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """

    # Application
    app_name: str = "ImageToSTL Converter API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"  # Listen on all interfaces for cloud deployment
    port: int = 8000

    # CORS - Frontend URLs
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]

    # Add production frontend URL here when deploying
    # Example: "https://your-app.vercel.app"

    # Color Processing
    default_layer_count: int = 4
    default_layer_height: float = 0.08
    default_pixel_size: float = 0.08
    default_max_colors: int = 10
    default_color_threshold: float = 50.0
    # Colors are seen against the image's white (core/white_point.py): the
    # mean of this share of its pixels closest to white. When that white is an
    # off-white (within off_white_max_delta_e CIEDE2000 of white) and the image
    # reaches deep shadows, colors are adapted from it to print white and
    # off-whites become white.
    white_point_share: float = 0.01
    off_white_max_delta_e: float = 15.0
    # Deep shadows: the darkest low_contrast_shadow_share of pixels are darker
    # than L* low_contrast_shadow_lightness. Faded, high-key and Morandi-palette
    # images stop above it and keep their colors (the darkest 5% measured L*
    # 0-27 in normal photos, 30-78 in muted palettes).
    low_contrast_shadow_share: float = 0.05
    low_contrast_shadow_lightness: float = 28.0

    # Parameter search runs after the request returns. It scores the current
    # settings and then this many other settings (services/param_search_service.py).
    param_search_trials: int = 20
    # Stop between candidates at this budget and keep all completed previews.
    param_search_job_budget_seconds: float = 1800.0
    # A job whose page stopped polling (closed, reloaded, crashed) stops after
    # its current candidate, so it cannot hold the only search slot. Hidden
    # browser tabs may poll only once a minute.
    param_search_abandon_seconds: float = 180.0

    # Model grid cell budget: larger images are resampled to at most this many
    # cells, which bounds processing, cleanup and export time (see
    # image_processor.model_pitch).
    max_model_cells: int = 2_000_000

    # File Upload
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]

    # Logging: "text" for local development, "json" in production (Dockerfile)
    # so Railway indexes each record's fields.
    log_level: str = "INFO"
    log_format: str = "text"

    # Per-client request limits. E2E runs disable them: one browser drives the
    # whole suite from a single address.
    rate_limit_enabled: bool = True

    # Visitor address for rate limiting and telemetry. Railway's edge sets this
    # header to the peer that connected to it; empty uses the socket peer.
    client_ip_header: str = "X-Real-IP"
    # Cloudflare's published edge ranges. CF-Connecting-IP is trusted only when
    # the peer is inside them; empty disables the Cloudflare header.
    cloudflare_ips_url: str = "https://api.cloudflare.com/client/v4/ips"
    cloudflare_ips_timeout_seconds: float = 5.0

    # Stack-search budget: full permutation enumeration (N^L codes) is used
    # whenever its probe-extrapolated wall time fits this budget; larger
    # translucent sets fall back to composition pruning, and larger opaque
    # sets are rejected. 60s matches the Railway edge request timeout that
    # bounds every sync endpoint anyway.
    full_enumeration_budget_seconds: float = 60.0
    # Ceiling on any stack search's estimated time, pruned or not: beyond it the
    # request is rejected rather than running into Cloudflare's 100 s origin
    # timeout.
    stack_search_limit_seconds: float = 80.0
    # Share of that ceiling a filament set's color-layer maximum may use,
    # leaving headroom for image processing and timing variance.
    layer_limit_budget_share: float = 0.5
    # Most target colors (pixel max colors, SVG colors) a request may use.
    max_target_colors: int = 100

    # Upper bound on worker threads for vectorized stack enumeration and color
    # matching (numpy releases the GIL). The startup probe uses fewer when the
    # host has fewer usable CPUs or threads do not help (core/parallel.py).
    compute_threads: int = 8

    # Reference-matrix cache budget in references across all entries (about
    # 150 bytes each as DataFrames). Presets need thousands; one custom set at
    # its layer limit can need millions (16 opaque colors x 6 layers: 2.8M).
    matrix_cache_max_references: int = 6_000_000

    # STL/3MF generation: cap on total merged boxes per request. Greedy meshing
    # collapses runs of same-color pixels, so the guard is enforced on the REAL
    # merged box count (cumulative across color blocks), not on the raw
    # pixel × layer estimate — a large but mergeable photo passes, while
    # noise-like content fails fast inside greedy_mesh_2d.
    # ~5M boxes ≈ the memory budget measured when OOM kills were fixed (d480ddf).
    stl_max_boxes: int = 5_000_000

    # Bug reports are saved locally before optional email delivery.
    bug_report_storage_dir: str = "bug-reports"
    resend_api_key: SecretStr = SecretStr("")
    resend_from: str = "onboarding@resend.dev"
    bug_report_email_to: str = ""

    # Cloud deployment settings
    # Set these via environment variables in production
    environment: str = "development"  # development, staging, production

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()


def get_cors_origins() -> list[str]:
    """
    Get CORS origins from settings
    In production, add custom origins via CORS_ORIGINS environment variable
    """
    # Check if custom CORS origins are provided via environment
    custom_origins = os.getenv("CORS_ORIGINS")
    if custom_origins:
        # Parse comma-separated origins
        return [origin.strip() for origin in custom_origins.split(",")]

    return settings.cors_origins


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.environment.lower() == "development"
