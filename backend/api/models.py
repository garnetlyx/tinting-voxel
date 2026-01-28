"""
Pydantic models for API request and response validation
"""
from enum import Enum

from pydantic import BaseModel, Field


class ProcessingMode(str, Enum):
    """Processing mode for image to STL conversion."""
    PIXEL = "pixel"
    SVG = "svg"


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
    pixels: list[PixelCoordinate]
    hex: str


class ImageDimensions(BaseModel):
    """Image dimensions in pixels"""
    width: int
    height: int


class ProcessImageResponse(BaseModel):
    """Response model for /api/process-image endpoint"""
    colorBlocks: list[ColorBlock]
    processedImage: str  # base64 encoded image
    imageDimensions: ImageDimensions


class DownloadCSVRequest(BaseModel):
    """Request model for /api/download-csv endpoint"""
    colorBlocks: list[ColorBlock]


class VectorColorResult(BaseModel):
    """Vector processing result for a single color."""
    color: tuple[int, int, int]
    polygons: list[list[tuple[float, float]]]
    pixel_count: int = Field(..., ge=0)
    polygon_points: int = Field(..., ge=0)


class SVGProcessImageResponse(BaseModel):
    """Response model for /api/process-image endpoint in SVG mode."""
    vectorResults: list[VectorColorResult]
    processedImage: str  # base64 encoded image
    imageDimensions: ImageDimensions


class DownloadSTLRequest(BaseModel):
    """Request model for /api/download-stl endpoint (pixel mode)."""
    colorBlocks: list[ColorBlock]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    mode: ProcessingMode = ProcessingMode.PIXEL


class DownloadSVGSTLRequest(BaseModel):
    """Request model for /api/download-stl endpoint (SVG mode)."""
    vectorResults: list[VectorColorResult]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
