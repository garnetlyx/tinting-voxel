"""
Pydantic models for API request and response validation
"""

from pydantic import BaseModel, Field


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


class DownloadSTLRequest(BaseModel):
    """Request model for /api/download-stl endpoint"""
    colorBlocks: list[ColorBlock]
    layerHeight: float = Field(..., gt=0)
    pixelSize: float = Field(..., gt=0)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
