"""
Pydantic models for API request and response validation
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class ProcessingMode(str, Enum):
    """Processing mode for image to STL conversion."""
    PIXEL = "pixel"
    SVG = "svg"


class FilamentColorConfig(BaseModel):
    """Configuration for a single filament color."""
    name: str = Field(..., min_length=1, description="Display name for the color")
    hex: str = Field(..., description="Hex color code (e.g., '#00FFFF')")
    transmission_distance: float = Field(
        ...,
        gt=0,
        description="Beer-Lambert transmission distance (opacity control)"
    )

    @validator('hex')
    def validate_hex(cls, v):
        """Validate hex color format."""
        hex_value = v.lstrip('#')
        if len(hex_value) != 6:
            raise ValueError(f"Invalid hex color format: {v}")
        try:
            int(hex_value, 16)
        except ValueError:
            raise ValueError(f"Invalid hex color format: {v}")
        return v

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


class FilamentPreset(str, Enum):
    """Available filament presets."""
    BAMBU_CMYK = "bambu_cmyk"
    CLEAR_CMYK = "clear_cmyk"


class PixelCoordinate(BaseModel):
    """Single pixel coordinate"""
    x: int
    y: int


class ColorBlock(BaseModel):
    """Color block with RGB values and pixel positions"""
    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)
    count: int = Field(..., ge=0)
    pixels: List[PixelCoordinate]
    hex: str


class ImageDimensions(BaseModel):
    """Image dimensions in pixels"""
    width: int
    height: int


class ProcessImageResponse(BaseModel):
    """Response model for /api/process-image endpoint"""
    colorBlocks: List[ColorBlock]
    processedImage: str  # base64 encoded image
    imageDimensions: ImageDimensions


class DownloadCSVRequest(BaseModel):
    """Request model for /api/download-csv endpoint"""
    colorBlocks: List[ColorBlock]


class VectorColorResult(BaseModel):
    """Vector processing result for a single color."""
    color: tuple
    polygons: List[List[tuple]]
    pixel_count: int = Field(..., ge=0)
    polygon_points: int = Field(..., ge=0)


class SVGProcessImageResponse(BaseModel):
    """Response model for /api/process-image endpoint in SVG mode."""
    vectorResults: List[VectorColorResult]
    processedImage: str  # base64 encoded image
    imageDimensions: ImageDimensions


class DownloadSTLRequest(BaseModel):
    """Request model for /api/download-stl endpoint (pixel mode)."""
    colorBlocks: List[ColorBlock]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    mode: ProcessingMode = ProcessingMode.PIXEL


class DownloadSVGSTLRequest(BaseModel):
    """Request model for /api/download-stl endpoint (SVG mode)."""
    vectorResults: List[VectorColorResult]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions


# V2 API Models with configurable colors
class DownloadSTLRequestV2(BaseModel):
    """Request model for /api/v2/download-stl endpoint with configurable colors."""
    colorBlocks: List[ColorBlock]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    mode: ProcessingMode = ProcessingMode.PIXEL
    filamentPreset: Optional[FilamentPreset] = None
    filamentColors: Optional[List[FilamentColorConfig]] = Field(
        None,
        min_items=4,
        max_items=10,
        description="Custom filament colors (4-10 colors)"
    )

    @validator('filamentColors')
    def validate_unique_labels(cls, v):
        """Ensure all filament colors have unique labels."""
        if v is None:
            return v
        labels = [c.name[0].upper() for c in v]
        if len(labels) != len(set(labels)):
            raise ValueError("Filament colors must have unique first letters")
        return v


class DownloadSVGSTLRequestV2(BaseModel):
    """Request model for /api/v2/download-svg-stl endpoint with configurable colors."""
    vectorResults: List[VectorColorResult]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    filamentPreset: Optional[FilamentPreset] = None
    filamentColors: Optional[List[FilamentColorConfig]] = Field(
        None,
        min_items=4,
        max_items=10,
        description="Custom filament colors (4-10 colors)"
    )

    @validator('filamentColors')
    def validate_unique_labels(cls, v):
        """Ensure all filament colors have unique labels."""
        if v is None:
            return v
        labels = [c.name[0].upper() for c in v]
        if len(labels) != len(set(labels)):
            raise ValueError("Filament colors must have unique first letters")
        return v


class FilamentPresetInfo(BaseModel):
    """Information about a filament preset."""
    name: str
    display_name: str
    colors: List[FilamentColorConfig]


class FilamentPresetsResponse(BaseModel):
    """Response model for /api/filament-presets endpoint."""
    presets: List[FilamentPresetInfo]
