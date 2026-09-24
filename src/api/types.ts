/**
 * TypeScript type definitions for API requests and responses
 */

export type ProcessingMode = 'pixel' | 'svg';

export interface PixelCoordinate {
  x: number;
  y: number;
}

export interface ColorBlock {
  r: number;
  g: number;
  b: number;
  count: number;
  pixels: PixelCoordinate[];
  hex: string;
}

export interface VectorColorResult {
  color: [number, number, number];
  regions: VectorRegion[];
  pixel_count: number;
  polygon_points: number;
}

export interface VectorRegion {
  outer: [number, number][];
  holes: [number, number][][];
}

export interface ImageDimensions {
  width: number;
  height: number;
}

export interface ProcessImageResponse {
  colorBlocks: ColorBlock[];
  processedImage: string;  // simulated printable image
  segmentationImage: string;  // quantized/merged source preview
  mappedBlockColors: MappedBlockColor[];
  mappedBlendPalette: MappedBlendPaletteEntry[];
  imageDimensions: ImageDimensions;
  pixelSize?: number;
  detailSize?: number;
  printStack: PrintStackInfo;
}

export interface SVGProcessImageResponse {
  vectorResults: VectorColorResult[];
  processedImage: string;  // simulated printable image
  segmentationImage: string;  // quantized/vectorized source preview
  mappedBlendPalette: MappedBlendPaletteEntry[];
  imageDimensions: ImageDimensions;
  pixelSize?: number;
  detailSize?: number;
  printStack: PrintStackInfo;
}

export interface PixelModeParams {
  maxColors: number;
  colorThreshold: number;
}

export interface SVGModeParams {
  epsilon: number;
  minArea: number;
  numColors: number;
}

export interface ProcessImageParams {
  mode: ProcessingMode;
  pixelSize: number;
  layerHeight?: number;
  layerCount?: number;
  whiteBackingLayers?: number;
  backingFilament?: FilamentLabel;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  pixelParams?: PixelModeParams;
  svgParams?: SVGModeParams;
  detailSize?: number;
}

export interface DownloadSTLParams {
  colorBlocks: ColorBlock[];
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  imageDimensions: ImageDimensions;
}

export interface DownloadSVGSTLParams {
  vectorResults: VectorColorResult[];
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  imageDimensions: ImageDimensions;
}

// V2 API types for configurable filament colors

export type FilamentPreset = string;
export type TransmissionDistance = number | [number, number, number];

export interface FilamentColorConfig {
  name: string;
  hex: string;
  transmission_distance: TransmissionDistance;
}

export const LAYER_HEIGHT_MIN_MM = 0.08;
export const LAYER_HEIGHT_MAX_MM = 0.84;

export interface FilamentPresetInfo {
  name: FilamentPreset;
  display_name: string;
  colors: FilamentColorConfig[];
}

export interface FilamentPresetsResponse {
  presets: FilamentPresetInfo[];
  defaults: {
    filament_preset: FilamentPreset;
    backing_layers: number;
    regular_layer_height_mm: number;
    transparent_layer_height_mm: number;
    max_model_cells: number;
    max_model_side_px: number;
    max_color_layers: number;
    max_target_colors: number;
  };
  transparency: {
    td_threshold_mm: number;
    aggregation: 'mean';
  };
}

export interface DownloadSTLParamsV2 extends DownloadSTLParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  whiteBackingLayers?: number;
  backingFilament?: FilamentLabel;
  detailSize?: number;
}

export interface DownloadSVGSTLParamsV2 extends DownloadSVGSTLParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  whiteBackingLayers?: number;
  backingFilament?: FilamentLabel;
  detailSize?: number;
}

export interface PrintSettingsParams {
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  imageDimensions: ImageDimensions;
  whiteBackingLayers?: number;
  backingFilament?: FilamentLabel;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  detailSize?: number;
}

export interface FilamentPreviewParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  layerCount: number;
  layerHeight: number;
  whiteBackingLayers: number;
  backingFilament?: FilamentLabel;
}

export interface ColorMatrixEntry {
  code: string;
  rgb: number[];
}

export interface MappedBlendPaletteEntry {
  code: string;
  rgb: number[];
  hex: string;
  sourceRgb: number[];
  sourceHex: string;
  pixelCount: number;
  pixelPercent: number;
}

export interface MappedBlockColor {
  code: string;
  rgb: number[];
  hex: string;
}

export interface FilamentPreviewResponse {
  image: string;
  colorMatrix: ColorMatrixEntry[];
  stats: { colorCount: number; combinationCount: number };
  imageDimensions: { width: number; height: number };
  warnings: string[];
}

export interface SimulatedPrintPreviewParams {
  colorBlocks: ColorBlock[];
  imageDimensions: ImageDimensions;
  layerHeight: number;
  layerCount: number;
  whiteBackingLayers?: number;
  backingFilament?: FilamentLabel;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
}

export interface SimulatedPrintPreviewResponse {
  processedImage: string;
  mappedBlockColors: MappedBlockColor[];
  mappedBlendPalette: MappedBlendPaletteEntry[];
  printStack: PrintStackInfo;
}

/** A filament's label: the first letter of its name, as in blend codes. */
export type FilamentLabel = string;

/** What the backend reports for a filament set (/api/v2/filament-set). */
export interface FilamentSetInfo {
  maxLayerCount: number;
  defaultBackingFilament: FilamentLabel;
}

export interface PrintStackInfo {
  opticalLayerCount: number;
  whiteBackingLayers: number;
  /** Filament printed as the backing block; null without backing layers. */
  backingFilament: FilamentLabel | null;
  totalLayerCount: number;
  totalHeightMm: number;
}

// Batch processing types

export interface BatchImageResult {
  filename: string;
  status: 'success' | 'error';
  colorBlocks?: ColorBlock[];
  processedImage?: string;
  imageDimensions?: ImageDimensions;
  error?: string;
}

export interface BatchProcessResponse {
  results: BatchImageResult[];
  totalImages: number;
  successCount: number;
  errorCount: number;
}

export interface BatchProcessParams {
  maxColors: number;
  colorThreshold: number;
  pixelSize: number;
  detailSize?: number;
}

export interface BatchDownloadSTLParams {
  maxColors: number;
  colorThreshold: number;
  pixelSize: number;
  layerHeight: number;
  layerCount: number;
  whiteBackingLayers: number;
  backingFilament?: FilamentLabel;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  detailSize?: number;
}

// Palette library types

export type PaletteColorInfo = FilamentColorConfig;

export interface PaletteInfo {
  id: string;
  name: string;
  description: string;
  colors: PaletteColorInfo[];
}

export interface PaletteLibraryResponse {
  palettes: PaletteInfo[];
}

// User-submitted bug reports contain diagnostics, never the source image by default.
export interface ConverterBugReportState {
  appMode: 'single' | 'batch';
  mode: ProcessingMode;
  pixelSize: number;
  layerHeight: number;
  layerCount: number;
  whiteBackingLayers: number;
  backingFilament?: FilamentLabel;
  imageWidth: number;
  imageHeight: number;
  colorCount: number;
  filamentPreset: string | null;
  processing: boolean;
  error: string | null;
}

export interface BugReportLog {
  level: 'info' | 'warn' | 'error';
  message: string;
  timestamp: string;
}

export interface BugReportContext {
  url: string;
  userAgent: string;
  language: string;
  timestamp: string;
  viewport: { width: number; height: number };
  converter: ConverterBugReportState;
  debugLogs: BugReportLog[];
}

export interface BugReportRequest {
  description: string;
  frontendContext: BugReportContext;
  screenshot?: string;
}

export interface BugReportResponse {
  success: boolean;
  reportId: string;
  delivery: 'email' | 'stored';
}
