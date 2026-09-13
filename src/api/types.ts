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
  polygons: [number, number][][];
  regions?: VectorRegion[];
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
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  pixelParams?: PixelModeParams;
  svgParams?: SVGModeParams;
  detailSize?: number;
  targetWidth?: number;
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

export type FilamentPreset =
  | 'bambu_cmywk_phase6'
  | 'bambu_cmyw_phase6'
  | 'clear_cmyw';

export const DEFAULT_FILAMENT_PRESET: FilamentPreset = 'bambu_cmywk_phase6';
export const FILAMENT_PRESET_OPTIONS: { value: FilamentPreset; label: string }[] = [
  { value: 'bambu_cmywk_phase6', label: 'Bambu CMYWK' },
  { value: 'bambu_cmyw_phase6', label: 'Bambu CMYW' },
  { value: 'clear_cmyw', label: 'Clear CMYW' },
];

export interface FilamentColorConfig {
  name: string;
  hex: string;
  /** Channel-neutral transmission distance (mm), base-10: t = 10^(-d/td). */
  transmission_distance: number;
  /** Optional pigment absorption gain; 0 blends as plain Beer-Lambert. */
  k?: number;
}

// Layer-height bounds shared by every filament set. 0.84 mm is the clear-track
// calibration convention: 3 × 0.28 mm print layers per color layer.
export const LAYER_HEIGHT_MIN_MM = 0.08;
export const LAYER_HEIGHT_MAX_MM = 0.84;
export const DEFAULT_LAYER_HEIGHT_MM = 0.08;
export const TRANSPARENT_LAYER_HEIGHT_MM = 0.84;
// Transparency threshold (mm) on the stored td scale — the same number the
// backend prune gate uses (core/stack_prune.py TRANSPARENT_TD_THRESHOLD_MM).
// A literal constant, not user-adjustable: it is a property of the
// calibrated data gap (bambu folded 0.27-0.61 vs clear means 4.7-18.0).
export const TRANSPARENT_TD_THRESHOLD_MM = 4.5;

/**
 * A filament set counts as transparent when every filament's td meets the
 * fixed threshold. Drives the layer-height default; never gates user input.
 */
export function isAllTransparentFilaments(colors: FilamentColorConfig[]): boolean {
  if (colors.length === 0) return false;
  return colors.every(c => c.transmission_distance >= TRANSPARENT_TD_THRESHOLD_MM);
}

export interface FilamentPresetInfo {
  name: FilamentPreset;
  display_name: string;
  colors: FilamentColorConfig[];
}

export interface FilamentPresetsResponse {
  presets: FilamentPresetInfo[];
}

export interface DownloadSTLParamsV2 extends DownloadSTLParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  whiteBackingLayers?: number;
  detailSize?: number;
}

export interface DownloadSVGSTLParamsV2 extends DownloadSVGSTLParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  whiteBackingLayers?: number;
  detailSize?: number;
}

export interface PrintSettingsParams {
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  imageDimensions: ImageDimensions;
  whiteBackingLayers?: number;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  detailSize?: number;
}

export interface FilamentPreviewParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  layerCount: number;
  layerHeight: number;
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
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
}

export interface SimulatedPrintPreviewResponse {
  processedImage: string;
  mappedBlockColors: MappedBlockColor[];
  mappedBlendPalette: MappedBlendPaletteEntry[];
  printStack: PrintStackInfo;
}

export interface PrintStackInfo {
  opticalLayerCount: number;
  whiteBackingLayers: number;
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

// Default presets for frontend initialization. Mirrors the backend's
// core/color_config.py — bambu tds are the exact fold of the Phase-6 fitted
// scatter (bit-identical blending), clear is the staircase mean CMYW set.
export const DEFAULT_PRESETS: Record<FilamentPreset, FilamentColorConfig[]> = {
  bambu_cmywk_phase6: [
    { name: 'Cyan',    hex: '#3D79C6', transmission_distance: 0.48447574859816506, k: 8.13 },
    { name: 'Magenta', hex: '#B3356E', transmission_distance: 0.5218499460436025,  k: 8.42 },
    { name: 'Yellow',  hex: '#FFE665', transmission_distance: 0.5819156593127012,  k: 3.73 },
    { name: 'White',   hex: '#FFFFFF', transmission_distance: 0.6055249051606083,  k: 12.39 },
    { name: 'Key',     hex: '#0B0F0C', transmission_distance: 0.26611297079931917, k: 17.65 },
  ],
  bambu_cmyw_phase6: [
    { name: 'Cyan',    hex: '#3D79C6', transmission_distance: 0.48447574859816506, k: 8.13 },
    { name: 'Magenta', hex: '#B3356E', transmission_distance: 0.5218499460436025,  k: 8.42 },
    { name: 'Yellow',  hex: '#FFE665', transmission_distance: 0.5819156593127012,  k: 3.73 },
    { name: 'White',   hex: '#FFFFFF', transmission_distance: 0.6055249051606083,  k: 12.39 },
  ],
  clear_cmyw: [
    { name: 'Cyan',    hex: '#5489B4', transmission_distance: 4.7,  k: 0 },
    { name: 'Magenta', hex: '#DE5740', transmission_distance: 6.3,  k: 0 },
    { name: 'Yellow',  hex: '#DDC465', transmission_distance: 10.1, k: 0 },
    { name: 'White',   hex: '#D9D6C5', transmission_distance: 18.0, k: 0 },
  ],
};

// User-submitted bug reports contain diagnostics, never the source image by default.
export interface ConverterBugReportState {
  appMode: 'single' | 'batch';
  mode: ProcessingMode;
  pixelSize: number;
  layerHeight: number;
  layerCount: number;
  whiteBackingLayers: number;
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
