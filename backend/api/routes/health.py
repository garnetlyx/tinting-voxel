"""
Health check and monitoring endpoints for cloud deployment
"""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint for load balancers and monitoring
    Returns 200 OK if service is healthy
    """
    return {
        "status": "healthy",
        "service": "tinting-voxel-api"
    }


@router.get("/api/health/detailed")
async def detailed_health_check() -> dict:
    """
    Detailed health check with service information
    Useful for debugging in cloud environments
    """
    return {
        "status": "healthy",
        "service": "tinting-voxel-api",
        "version": "1.0.0"
    }
