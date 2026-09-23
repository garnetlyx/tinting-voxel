"""
Pydantic models for API request and response validation
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
from core.color_config import normalize_transmission_distance
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


class ProcessingMode(str, Enum):
    """Processing mode for image to STL conversion."""
    PIXEL = "pixel"
    SVG = "svg"


class FilamentColorConfig(BaseModel):
    """A material color and one scalar or RGB transmission-distance value."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=200)
    hex: str
    transmission_distance: float | tuple[float, float, float]

    @field_validator('transmission_distance', mode='before')
    @classmethod
    def validate_transmission_distance(cls, value):
        value = normalize_transmission_distance(value)
        values = value if isinstance(value, tuple) else (value,)
        if any(not (0 < td <= 1000) for td in values):
            raise ValueError("TD values must be finite and in (0, 1000] mm")
        return value

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Reject whitespace-only names and strip leading/trailing whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be whitespace-only")
        # Name must start with an ASCII letter (A-Z or a-z)
        # The first character becomes the blend code, which must be ASCII
        if not stripped[0].isalpha() or not stripped[0].isascii():
            raise ValueError(
                f"Name must start with an ASCII letter (A-Z, a-z): {stripped}. "
                f"The first character is used as the blend code identifier."
            )
        return stripped

    @field_validator('hex')
    @classmethod
    def validate_hex(cls, v):
        """Validate hex color format. Requires exactly '#' followed by 6 hex digits."""
        import re
        if not re.match(r'^#[0-9a-fA-F]{6}$', v):
            raise ValueError(f"Invalid hex color format: {v}. Must be '#' followed by 6 hex digits (e.g., '#00FFFF')")
        return v

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


class FilamentPreset(str, Enum):
    """Available filament presets."""
    BAMBU_CMYWK = "bambu_cmywk"
    BAMBU_CMYW = "bambu_cmyw"
    CLEAR_CMYG = "clear_cmyg"
    CLEAR_CMYW = "clear_cmyw"


class PixelCoordinate(BaseModel):
    """Single pixel coordinate"""
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)


class ColorBlock(BaseModel):
    """Color block with RGB values and pixel positions"""
    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)
    pixels: List[PixelCoordinate] = Field(..., min_length=1, max_length=1048576)
    count: int = Field(..., ge=1)
    hex: str

    @field_validator('hex')
    @classmethod
    def validate_hex(cls, v):
        """Validate hex color format."""
        import re
        if not re.match(r'^#[0-9a-fA-F]{6}$', v):
            raise ValueError(f"Invalid hex color format: {v}. Must be '#' followed by 6 hex digits")
        return v

    @field_validator('count')
    @classmethod
    def validate_count_matches_pixels(cls, v, info):
        """Ensure count matches the number of pixels."""
        # Pydantic V2: use info.data instead of values
        pixels = info.data.get('pixels')
        if pixels is not None and v != len(pixels):
            raise ValueError(
                f"count ({v}) does not match number of pixels ({len(pixels)})"
            )
        return v


class ImageDimensions(BaseModel):
    """Image dimensions in pixels"""
    width: int = Field(..., gt=0, le=10000)
    height: int = Field(..., gt=0, le=10000)


class ProcessImageResponse(BaseModel):
    """Response model for /api/process-image endpoint"""
    colorBlocks: List[ColorBlock]
    processedImage: str  # base64 encoded simulated print preview
    segmentationImage: str  # base64 encoded quantized/merged preview
    mappedBlockColors: List["MappedBlockColor"]
    mappedBlendPalette: List["MappedBlendPaletteEntry"]
    imageDimensions: ImageDimensions
    pixelSize: Optional[float] = None  # Actual pixel size used for model dimensions
    detailSize: Optional[float] = None  # Local detail merge threshold used in pixel mode
    printStack: "PrintStackInfo"


class DownloadCSVRequest(BaseModel):
    """Request model for /api/download-csv endpoint"""
    colorBlocks: List[ColorBlock] = Field(..., min_length=1)


class VectorRegion(BaseModel):
    """A single vector region with one exterior ring and optional holes."""
    outer: List[tuple[float, float]] = Field(..., min_length=3)
    holes: List[List[tuple[float, float]]] = Field(default_factory=list)


class VectorColorResult(BaseModel):
    """Vector processing result for a single color."""
    model_config = ConfigDict(extra="forbid")
    color: tuple[int, int, int]
    regions: List[VectorRegion] = Field(..., min_length=1)
    pixel_count: int = Field(..., ge=0)
    polygon_points: int = Field(..., ge=0)


class SVGProcessImageResponse(BaseModel):
    """Response model for /api/process-image endpoint in SVG mode."""
    vectorResults: List[VectorColorResult]
    processedImage: str  # base64 encoded simulated print preview
    segmentationImage: str  # base64 encoded quantized preview with contour overlay
    mappedBlendPalette: List["MappedBlendPaletteEntry"]
    imageDimensions: ImageDimensions
    pixelSize: Optional[float] = None
    detailSize: Optional[float] = None
    printStack: "PrintStackInfo"


# Shared mixin for filament configuration validation
class FilamentConfigMixin(BaseModel):
    """Mixin providing filament preset/custom color fields and validators."""
    filamentPreset: Optional[FilamentPreset] = None
    filamentColors: Optional[List[FilamentColorConfig]] = Field(
        None,
        min_length=4,
        max_length=16,
        description="Custom filament colors (4-16 colors)"
    )

    @field_validator('filamentColors')
    @classmethod
    def validate_unique_labels(cls, v):
        """Ensure all filament colors have unique labels and hex values."""
        if v is None:
            return v
        labels = [c.name[0].upper() for c in v]
        if len(labels) != len(set(labels)):
            raise ValueError("Filament colors must have unique first letters")
        hex_values = [c.hex.lower() for c in v]
        if len(hex_values) != len(set(hex_values)):
            raise ValueError("Filament colors must have unique hex values")
        return v

    @model_validator(mode='after')
    def validate_preset_or_custom_not_both(self):
        """Reject requests that provide both preset and custom colors."""
        if self.filamentPreset is not None and self.filamentColors is not None:
            raise ValueError(
                "Cannot provide both filamentPreset and filamentColors. Use one or the other."
            )
        return self


class PrintConfigMixin(FilamentConfigMixin):
    """Resolve omitted color-layer height from the selected material data."""
    layerHeight: Optional[float] = Field(None, gt=0, le=10)
    _resolved_colors: object = PrivateAttr()

    @model_validator(mode='after')
    def resolve_print_configuration(self):
        from api.filament_payload import get_colors_from_request, resolve_layer_height

        self._resolved_colors = get_colors_from_request(self.filamentPreset, self.filamentColors)
        self.layerHeight = resolve_layer_height(self.layerHeight, self._resolved_colors)
        return self

    @property
    def resolved_colors(self):
        return self._resolved_colors


class WhiteBackingMixin(BaseModel):
    """Mixin for explicit printed backing configuration (white or black block)."""
    whiteBackingLayers: int = Field(
        DEFAULT_BACKING_LAYERS,
        ge=0,
        le=5,
        description="Number of full-area backing layers printed behind the optical stack"
    )
    backingMode: Literal['white', 'black'] = Field(
        'white',
        description="Backing block filament: closest-to-white or closest-to-black in the set"
    )


# V2 API Models with configurable colors
class DownloadSTLRequestV2(PrintConfigMixin, WhiteBackingMixin):
    """Request model for /api/v2/download-stl endpoint with configurable colors."""
    colorBlocks: List[ColorBlock] = Field(..., min_length=1)
    pixelSize: float = Field(..., gt=0, le=10)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    mode: ProcessingMode = ProcessingMode.PIXEL
    detailSize: Optional[float] = Field(
        None, ge=0.2, le=0.8,
        description="Minimum physical pixel size in mm (default: 0.4)"
    )

    # No longer validate pixelSize >= detailSize
    # Small pixels will be merged at the backend level


class DownloadSVGSTLRequestV2(PrintConfigMixin, WhiteBackingMixin):
    """Request model for /api/v2/download-svg-stl endpoint with configurable colors."""
    vectorResults: List[VectorColorResult] = Field(..., min_length=1)
    pixelSize: float = Field(..., gt=0, le=10)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    detailSize: Optional[float] = Field(
        None, ge=0.2, le=0.9,
        description="Minimum printable feature width in mm"
    )


class FilamentPresetInfo(BaseModel):
    """Information about a filament preset."""
    name: str
    display_name: str
    colors: List[FilamentColorConfig]


class FilamentPresetsResponse(BaseModel):
    """Response model for /api/filament-presets endpoint."""
    presets: List[FilamentPresetInfo]
    defaults: dict
    transparency: dict


class FilamentPreviewRequest(PrintConfigMixin, WhiteBackingMixin):
    """Request model for /api/filament-preview endpoint."""
    layerCount: int = Field(4, ge=1, le=10)
    page: Optional[int] = Field(None, ge=1, description="Page number (1-based) for paginated results")
    pageSize: Optional[int] = Field(None, ge=1, le=10000, description="Number of entries per page")

    @model_validator(mode='after')
    def validate_preview_constraints(self):
        """Require at least one color source and validate pagination params."""
        if self.filamentPreset is None and self.filamentColors is None:
            raise ValueError(
                "Must provide either filamentPreset or filamentColors."
            )
        if (self.page is None) != (self.pageSize is None):
            raise ValueError(
                "page and pageSize must both be provided or both be omitted."
            )
        return self


class PrintStackInfo(BaseModel):
    """Actual exported stack metadata."""
    opticalLayerCount: int = Field(..., ge=0)
    whiteBackingLayers: int = Field(..., ge=0)
    backingMode: Literal['white', 'black'] = 'white'
    totalLayerCount: int = Field(..., ge=0)
    totalHeightMm: float = Field(..., ge=0)


class PrintSettingsRequest(PrintConfigMixin, WhiteBackingMixin):
    """Request model for /api/v2/print-settings endpoint."""
    pixelSize: float = Field(..., gt=0, le=10)
    layerCount: int = Field(..., ge=1, le=10)
    imageDimensions: ImageDimensions
    detailSize: Optional[float] = Field(
        None, ge=0.2, le=0.8,
        description="Minimum physical pixel size in mm (default: 0.4)"
    )

    # No longer validate pixelSize >= detailSize
    # Small pixels will be merged at the backend level


class ColorMatrixEntry(BaseModel):
    """Single entry in the color matrix."""
    code: str
    rgb: List[int]


class MappedBlendPaletteEntry(BaseModel):
    """Single source-color to printable-blend mapping."""
    code: str
    rgb: List[int]
    hex: str
    sourceRgb: List[int]
    sourceHex: str
    pixelCount: int = Field(..., ge=1)
    pixelPercent: float = Field(..., ge=0, le=100)


class MappedBlockColor(BaseModel):
    """Printable color assigned to a source block, preserving block order."""
    code: str
    rgb: List[int]
    hex: str


class SearchResultItem(BaseModel):
    """Single evaluated parameter combination."""
    candidate_id: int
    is_baseline: bool
    mode: str
    params: dict
    preview_image: str  # data URL (base64 PNG)


class ParamSearchResponse(BaseModel):
    """Snapshot of an asynchronous parameter search job."""
    job_id: str
    completed: int
    total: int
    status: Literal['running', 'complete', 'cancelled', 'error']
    settled: bool
    error: Optional[str] = None
    results: List[SearchResultItem]


class PaginationInfo(BaseModel):
    """Pagination metadata for paginated responses."""
    page: int
    pageSize: int
    totalCombinations: int
    totalPages: int


class FilamentPreviewResponse(BaseModel):
    """Response model for /api/filament-preview endpoint."""
    image: str  # base64 encoded PNG
    colorMatrix: List[ColorMatrixEntry]
    stats: dict
    imageDimensions: dict
    warnings: List[str] = []
    pagination: Optional[PaginationInfo] = None


class SimulatePreviewRequest(PrintConfigMixin):
    """Request model for print-simulation preview generation."""
    colorBlocks: List[ColorBlock] = Field(..., min_length=1)
    imageDimensions: ImageDimensions
    layerCount: int = Field(4, ge=1, le=10)
    whiteBackingLayers: int = Field(DEFAULT_BACKING_LAYERS, ge=0, le=5)
    backingMode: Literal['white', 'black'] = 'white'


class SimulatedPrintPreviewResponse(BaseModel):
    """Response model for print-simulation preview generation."""
    processedImage: str  # base64 encoded simulated print preview
    mappedBlockColors: List[MappedBlockColor]
    mappedBlendPalette: List[MappedBlendPaletteEntry]
    printStack: PrintStackInfo


ProcessImageResponse.model_rebuild()


class BatchImageResult(BaseModel):
    """Result for a single image in a batch processing request."""
    filename: str
    status: str = Field(..., description="'success' or 'error'")
    colorBlocks: Optional[List[ColorBlock]] = None
    processedImage: Optional[str] = None
    imageDimensions: Optional[ImageDimensions] = None
    error: Optional[str] = None


class BatchProcessResponse(BaseModel):
    """Response model for batch image processing."""
    results: List[BatchImageResult]
    totalImages: int
    successCount: int
    errorCount: int


class PaletteColorInfo(FilamentColorConfig):
    """Palette colors use the same complete material contract as presets."""


class PaletteInfo(BaseModel):
    """A single palette in the library."""
    id: str
    name: str
    description: str
    colors: List[PaletteColorInfo]


class PaletteLibraryResponse(BaseModel):
    """Response model for palette library listing."""
    palettes: List[PaletteInfo]


class BugReportLog(BaseModel):
    """One bounded browser diagnostic entry."""
    level: str = Field(..., pattern=r'^(info|warn|error)$')
    message: str = Field(..., max_length=1000)
    timestamp: str = Field(..., max_length=50)


class BugReportViewport(BaseModel):
    width: int = Field(0, ge=0, le=100000)
    height: int = Field(0, ge=0, le=100000)


class BugReportConverterState(BaseModel):
    """Allowlisted conversion details; no source files or pixel payloads."""
    appMode: str = Field('single', pattern=r'^(single|batch)$')
    mode: ProcessingMode = ProcessingMode.PIXEL
    pixelSize: float = Field(0, ge=0, le=1000)
    layerHeight: float = Field(0, ge=0, le=1000)
    layerCount: int = Field(0, ge=0, le=10000)
    whiteBackingLayers: int = Field(0, ge=0, le=10000)
    backingMode: Literal['white', 'black'] = 'white'
    imageWidth: int = Field(0, ge=0, le=100000)
    imageHeight: int = Field(0, ge=0, le=100000)
    colorCount: int = Field(0, ge=0, le=1000000)
    filamentPreset: Optional[str] = Field(None, max_length=100)
    processing: bool = False
    error: Optional[str] = Field(None, max_length=1000)


class BugReportContext(BaseModel):
    url: str = Field('', max_length=2000)
    userAgent: str = Field('', max_length=500)
    language: str = Field('', max_length=40)
    timestamp: str = Field('', max_length=50)
    viewport: BugReportViewport = Field(default_factory=BugReportViewport)
    converter: BugReportConverterState = Field(default_factory=BugReportConverterState)
    debugLogs: List[BugReportLog] = Field(default_factory=list, max_length=100)


class BugReportRequest(BaseModel):
    description: str = Field('', max_length=1000)
    frontendContext: BugReportContext = Field(default_factory=BugReportContext)
    screenshot: Optional[str] = Field(None, max_length=5 * 1024 * 1024)
