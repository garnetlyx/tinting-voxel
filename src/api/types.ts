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
  | 'clear_cmywg';

export const DEFAULT_FILAMENT_PRESET: FilamentPreset = 'bambu_cmywk_phase6';
export const FILAMENT_PRESET_OPTIONS: { value: FilamentPreset; label: string }[] = [
  { value: 'bambu_cmywk_phase6', label: 'Bambu CMYWK' },
  { value: 'bambu_cmyw_phase6', label: 'Bambu CMYW' },
  { value: 'clear_cmywg', label: 'Clear CMYWG' },
];

export interface FilamentColorConfig {
  name: string;
  hex: string;
  transmission_distance: number;
  alpha?: number;
  k?: number;
  td_rgb?: [number, number, number];
  /** Neutral (dye-free) transmission distance (TD1S strand measurement), mm. */
  td_neutral?: number;
  td_scale?: number;
  td_gamma?: number;
}

// Layer-height bounds shared by every filament set. 0.84 mm is the clear-track
// calibration convention: 3 × 0.28 mm print layers per color layer.
export const LAYER_HEIGHT_MIN_MM = 0.08;
export const LAYER_HEIGHT_MAX_MM = 0.84;
export const DEFAULT_LAYER_HEIGHT_MM = 0.08;
export const TRANSPARENT_LAYER_HEIGHT_MM = 0.84;
// Default transparency threshold from TD1S strand measurements: highest
// opaque filament TD1S is White 6.1, lowest transparent is Panchroma grey 7.3;
// 6.7 is their midpoint and separates all measured data with margin.
export const DEFAULT_TRANSPARENT_TD_THRESHOLD_MM = 6.7;

/**
 * A filament set counts as transparent when every filament's neutral TD
 * (td_neutral when measured, else the config transmission distance) meets the
 * threshold. Drives the layer-height default; never gates user input.
 */
export function isAllTransparentFilaments(
  colors: FilamentColorConfig[],
  thresholdMm: number,
): boolean {
  if (colors.length === 0) return false;
  return colors.every(c => (c.td_neutral ?? c.transmission_distance) >= thresholdMm);
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
  doubleSided?: boolean;
  detailSize?: number;
}

export interface DownloadSVGSTLParamsV2 extends DownloadSVGSTLParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  whiteBackingLayers?: number;
  doubleSided?: boolean;
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
  doubleSided: boolean;
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

// Default presets for frontend initialization
export const DEFAULT_PRESETS: Record<FilamentPreset, FilamentColorConfig[]> = {
  bambu_cmywk_phase6: [
    {
      name: 'Cyan',
      hex: '#3D79C6',
      transmission_distance: 2.0,
      td_neutral: 2.0,
      alpha: 8.08,
      k: 8.13,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'Magenta',
      hex: '#B3356E',
      transmission_distance: 2.9,
      td_neutral: 2.9,
      alpha: 8.08,
      k: 8.42,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'Yellow',
      hex: '#FFE665',
      transmission_distance: 5.0,
      td_neutral: 5.0,
      alpha: 8.08,
      k: 3.73,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'White',
      hex: '#FFFFFF',
      transmission_distance: 6.1,
      td_neutral: 6.1,
      alpha: 8.08,
      k: 12.39,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'Key',
      hex: '#0B0F0C',
      transmission_distance: 0.1,
      td_neutral: 0.1,
      alpha: 8.08,
      k: 17.65,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
  ],
  bambu_cmyw_phase6: [
    {
      name: 'Cyan',
      hex: '#3D79C6',
      transmission_distance: 2.0,
      td_neutral: 2.0,
      alpha: 8.08,
      k: 8.13,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'Magenta',
      hex: '#B3356E',
      transmission_distance: 2.9,
      td_neutral: 2.9,
      alpha: 8.08,
      k: 8.42,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'Yellow',
      hex: '#FFE665',
      transmission_distance: 5.0,
      td_neutral: 5.0,
      alpha: 8.08,
      k: 3.73,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
    {
      name: 'White',
      hex: '#FFFFFF',
      transmission_distance: 6.1,
      td_neutral: 6.1,
      alpha: 8.08,
      k: 12.39,
      td_scale: 1.48,
      td_gamma: 0.20,
    },
  ],
  clear_cmywg: [
    {
      name: 'Cyan',
      hex: '#5489B4',
      transmission_distance: 4.7,
      td_neutral: 48.9,
      alpha: 12.0,
      k: 1.93,
      td_rgb: [1.04, 4.66, 8.30],
      td_scale: 1.0,
      td_gamma: 1.0,
    },
    {
      name: 'Magenta',
      hex: '#DE5740',
      transmission_distance: 6.3,
      td_neutral: 100,
      alpha: 12.0,
      k: 1.44,
      td_rgb: [12.87, 2.39, 3.70],
      td_scale: 1.0,
      td_gamma: 1.0,
    },
    {
      name: 'Yellow',
      hex: '#DDC465',
      transmission_distance: 10.1,
      td_neutral: 100,
      alpha: 12.0,
      k: 0.67,
      td_rgb: [15.13, 12.29, 2.81],
      td_scale: 1.0,
      td_gamma: 1.0,
    },
    {
      name: 'White',
      hex: '#D9D6C5',
      transmission_distance: 18.0,
      td_neutral: 100,
      alpha: 12.0,
      k: 0.11,
      td_rgb: [17.95, 18.90, 17.21],
      td_scale: 1.0,
      td_gamma: 1.0,
    },
    {
      name: 'Grey',
      hex: '#9A9D9C',
      transmission_distance: 1.7,
      td_neutral: 7.3,
      alpha: 12.0,
      k: 10.0,
      td_rgb: [2.23, 1.69, 1.19],
      td_scale: 1.0,
      td_gamma: 1.0,
    },
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
  doubleSided: boolean;
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
