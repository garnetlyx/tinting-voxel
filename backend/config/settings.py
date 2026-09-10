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

    # Param search: wall-clock budget per run. Must stay below the Railway edge
    # request timeout (~60s observed); the endpoint returns the best partial
    # results collected within this budget.
    param_search_budget_seconds: float = 50.0

    # File Upload
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]

    # Logging
    log_level: str = "INFO"

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
