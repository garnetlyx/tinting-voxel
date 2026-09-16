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
  | 'clear_cmyg'
  | 'clear_cmyw';

export const DEFAULT_FILAMENT_PRESET: FilamentPreset = 'bambu_cmywk_phase6';
export const FILAMENT_PRESET_OPTIONS: { value: FilamentPreset; label: string }[] = [
  { value: 'bambu_cmywk_phase6', label: 'Bambu CMYWK' },
  { value: 'bambu_cmyw_phase6', label: 'Bambu CMYW' },
  { value: 'clear_cmyg', label: 'Clear CMYG' },
  { value: 'clear_cmyw', label: 'Clear CMYW' },
];

export interface FilamentColorConfig {
  name: string;
  hex: string;
  /** Channel-neutral transmission distance (mm). Raw scalar TD reading;
   * remapped by td_scale/td_gamma (paper Eq. (2)) in the scalar form. */
  transmission_distance: number;
  /** Staircase-measured per-channel transmission distances [R, G, B]
   * (mm); present means the per-channel form (mu = ln10/td_ch + k*A_ch). */
  td_rgb?: number[];
  /** Optional pigment absorption gain; 0 blends as plain Beer-Lambert. */
  k?: number;
  /** Scalar-form capture compensation (paper Eqs. (1)-(2)):
   * mu_ch = alpha_s/(td_scale * td**td_gamma) + k*A_ch. Neutral defaults
   * (alpha_s = ln 10, td_scale = td_gamma = 1) degrade to ln(10)/td. */
  alpha_s?: number;
  td_scale?: number;
  td_gamma?: number;
}

// Layer-height bounds shared by every filament set. 0.84 mm is the clear-track
// calibration convention: 3 × 0.28 mm print layers per color layer.
export const LAYER_HEIGHT_MIN_MM = 0.08;
export const LAYER_HEIGHT_MAX_MM = 0.84;
export const DEFAULT_LAYER_HEIGHT_MM = 0.08;
export const TRANSPARENT_LAYER_HEIGHT_MM = 0.84;
// Bambu A-standard calibration layer height (PLATE-06-H2C-A,
// research fitted_params.json layer_height_mm). The paper fit is
// process-conditioned: predictions are calibrated at this layer height.
export const BAMBU_LAYER_HEIGHT_MM = 0.32;
// Transparency threshold (mm) on the EFFECTIVE td scale — the same value the
// backend prune gate uses (core/stack_prune.py TRANSPARENT_TD_THRESHOLD_MM).
// Scalar tds are compared after the Eq. (2) remap (td_scale * td ** td_gamma).
export const TRANSPARENT_TD_THRESHOLD_MM = 4.5;

/**
 * A filament set counts as transparent when every filament's td data
 * indicates the transparent track: staircase-measured per-channel td_rgb,
 * or a scalar td whose EFFECTIVE value (td_scale * td ** td_gamma, paper
 * Eq. (2)) meets the fixed threshold. Drives the layer-height default;
 * never gates user input.
 */
export function isAllTransparentFilaments(colors: FilamentColorConfig[]): boolean {
  if (colors.length === 0) return false;
  return colors.every(c => {
    if (Array.isArray(c.td_rgb) && c.td_rgb.length === 3) return true;
    const td = c.transmission_distance;
    if (!(td > 0)) return false;
    const scale = c.td_scale ?? 1.0;
    const gamma = c.td_gamma ?? 1.0;
    return scale * Math.pow(td, gamma) >= TRANSPARENT_TD_THRESHOLD_MM;
  });
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
// core/color_config.py — bambu colors carry the raw scalar TDs of the
// paper's PLATE-06-H2C-A standard fit plus the composed capture
// compensation (paper Eqs. (1)-(2), see backend provenance comment);
// clear presets carry the staircase-measured per-channel td_rgb (paper
// form (i)).
// Bambu A-standard paper fit (PLATE-06-H2C-A): raw scalar TDs + composed
// capture compensation (alpha_s / td_scale / td_gamma, see backend
// core/color_config.py provenance comment). Calibrated at lh 0.32 mm.
const BAMBU_A = { alpha_s: 2.2292, td_scale: 2.023552983514602, td_gamma: 0.03272 };

export const DEFAULT_PRESETS: Record<FilamentPreset, FilamentColorConfig[]> = {
  bambu_cmywk_phase6: [
    { name: 'Cyan',    hex: '#3D79C6', transmission_distance: 2.0, k: 3.4996, ...BAMBU_A },
    { name: 'Magenta', hex: '#B3356E', transmission_distance: 2.9, k: 4.3077, ...BAMBU_A },
    { name: 'Yellow',  hex: '#FFE665', transmission_distance: 5.0, k: 3.6572, ...BAMBU_A },
    { name: 'White',   hex: '#FFFFFF', transmission_distance: 6.1, k: 6.3168, ...BAMBU_A },
    { name: 'Key',     hex: '#0B0F0C', transmission_distance: 0.1, k: 23.1863, ...BAMBU_A },
  ],
  bambu_cmyw_phase6: [
    { name: 'Cyan',    hex: '#3D79C6', transmission_distance: 2.0, k: 3.4996, ...BAMBU_A },
    { name: 'Magenta', hex: '#B3356E', transmission_distance: 2.9, k: 4.3077, ...BAMBU_A },
    { name: 'Yellow',  hex: '#FFE665', transmission_distance: 5.0, k: 3.6572, ...BAMBU_A },
    { name: 'White',   hex: '#FFFFFF', transmission_distance: 6.1, k: 6.3168, ...BAMBU_A },
  ],
  clear_cmyg: [
    { name: 'Cyan',    hex: '#5489B4', transmission_distance: 4.667418746800521,  td_rgb: [1.039647851596278, 4.661388851322945, 8.301219537482337], k: 0 },
    { name: 'Magenta', hex: '#DE5740', transmission_distance: 6.31945243505504,   td_rgb: [12.871171884721239, 2.3866487980887325, 3.700536622355147], k: 0 },
    { name: 'Yellow',  hex: '#DDC465', transmission_distance: 10.074691453694577, td_rgb: [15.128418453030553, 12.290455104172315, 2.8052008038808633], k: 0 },
    { name: 'Grey',    hex: '#9A9D9C', transmission_distance: 1.7030698349645412, td_rgb: [2.226964674889777, 1.688155998369564, 1.1940888316342828], k: 0 },
  ],
  clear_cmyw: [
    { name: 'Cyan',    hex: '#4C72A0', transmission_distance: 2.6582813347278655, td_rgb: [1.3490352079515975, 2.5371501740106988, 4.088658622221301], k: 0 },
    { name: 'Magenta', hex: '#CE5E53', transmission_distance: 5.252097918532708,  td_rgb: [11.210903332862577, 2.0338821311932, 2.511508291542347], k: 0 },
    { name: 'Yellow',  hex: '#D8B695', transmission_distance: 14.295863422405146, td_rgb: [22.124563670499846, 15.378730904545765, 5.384295692169828], k: 0 },
    { name: 'White',   hex: '#D9D6C5', transmission_distance: 18.02000330638548,  td_rgb: [17.949461574719358, 18.902845340687115, 17.207703003749966], k: 0 },
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
