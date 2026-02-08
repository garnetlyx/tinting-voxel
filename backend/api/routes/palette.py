"""
Color palette library endpoints.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import PaletteColorInfo, PaletteInfo, PaletteLibraryResponse
from api.rate_limiter import limiter
from core.palette_library import (
    ALL_PALETTES,
    CATEGORIES,
    get_palette,
    get_palettes_by_category,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/palettes", tags=["Palette Library"])


def _palette_to_info(entry) -> PaletteInfo:
    """Convert a PaletteEntry to PaletteInfo response model."""
    return PaletteInfo(
        id=entry.id,
        name=entry.name,
        description=entry.description,
        category=entry.category,
        colors=[
            PaletteColorInfo(
                name=c.name,
                hex=c.hex,
                transmission_distance=c.transmission_distance,
            )
            for c in entry.colors
        ],
    )


@router.get("/", response_model=PaletteLibraryResponse)
@limiter.limit("30/minute")
async def api_list_palettes(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    List available color palettes.

    Optionally filter by category: standard, artistic, specialty.

    Returns:
        PaletteLibraryResponse with palettes and category descriptions
    """
    if category:
        if category not in CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown category: '{category}'. Available: {', '.join(CATEGORIES.keys())}",
            )
        palettes = get_palettes_by_category(category)
    else:
        palettes = ALL_PALETTES

    return PaletteLibraryResponse(
        palettes=[_palette_to_info(p) for p in palettes],
        categories=CATEGORIES,
    )


@router.get("/{palette_id}", response_model=PaletteInfo)
@limiter.limit("30/minute")
async def api_get_palette(request: Request, palette_id: str):
    """
    Get a specific palette by ID.

    Args:
        palette_id: The palette identifier

    Returns:
        PaletteInfo with color configuration
    """
    entry = get_palette(palette_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Palette '{palette_id}' not found",
        )
    return _palette_to_info(entry)
