"""
Color palette library endpoints.
"""
import logging

from fastapi import APIRouter, HTTPException, Request

from api.models import PaletteColorInfo, PaletteInfo, PaletteLibraryResponse
from api.rate_limiter import limiter
from core.palette_library import (
    ALL_PALETTES,
    get_palette,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/palettes", tags=["Palette Library"])


def _palette_to_info(entry) -> PaletteInfo:
    """Convert a PaletteEntry to PaletteInfo response model."""
    return PaletteInfo(
        id=entry.id,
        name=entry.name,
        description=entry.description,
        colors=[
            PaletteColorInfo(
                name=c.name,
                hex=c.hex,
                transmission_distance=c.transmission_distance,
                td_rgb=c.td_rgb,
                k=c.k,
                alpha_s=getattr(c, "alpha_s", None),
                td_scale=getattr(c, "td_scale", None),
                td_gamma=getattr(c, "td_gamma", None),
            )
            for c in entry.colors
        ],
    )


@router.get("/", response_model=PaletteLibraryResponse)
@limiter.limit("30/minute")
async def api_list_palettes(
    request: Request,
):
    """
    List available color palettes.

    Returns:
        PaletteLibraryResponse with the two supported filament palettes
    """
    return PaletteLibraryResponse(
        palettes=[_palette_to_info(p) for p in ALL_PALETTES],
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
