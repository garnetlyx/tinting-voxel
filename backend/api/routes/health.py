"""
Health check and monitoring endpoints for cloud deployment
"""
from fastapi import APIRouter
from typing import Dict
import platform
import sys

router = APIRouter(tags=["Health"])


@router.get("/")
async def root() -> Dict[str, str]:
    """
    Root endpoint - basic health check
    """
    return {
        "status": "ok",
        "message": "ImageToSTL Converter API"
    }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for load balancers and monitoring
    Returns 200 OK if service is healthy
    """
    return {
        "status": "healthy",
        "service": "img2stl-api"
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict:
    """
    Detailed health check with system information
    Useful for debugging in cloud environments
    """
    return {
        "status": "healthy",
        "service": "img2stl-api",
        "version": "1.0.0",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.system(),
        "platform_release": platform.release()
    }
