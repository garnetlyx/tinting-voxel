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
  pixel_count: number;
  polygon_points: number;
}

export interface ImageDimensions {
  width: number;
  height: number;
}

export interface ProcessImageResponse {
  colorBlocks: ColorBlock[];
  processedImage: string;  // base64 encoded data URL
  imageDimensions: ImageDimensions;
  pixelSize?: number;
  detailSize?: number;
}

export interface SVGProcessImageResponse {
  vectorResults: VectorColorResult[];
  processedImage: string;  // base64 encoded data URL
  imageDimensions: ImageDimensions;
  pixelSize?: number;
  detailSize?: number;
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

export type FilamentPreset = 'bambu_cmyk' | 'clear_cmyk';

export interface FilamentColorConfig {
  name: string;
  hex: string;
  transmission_distance: number;
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
  basePlateThickness?: number;
  doubleSided?: boolean;
  detailSize?: number;
}

export interface DownloadSVGSTLParamsV2 extends DownloadSVGSTLParams {
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  basePlateThickness?: number;
  doubleSided?: boolean;
  detailSize?: number;
}

export interface PrintSettingsParams {
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  imageDimensions: ImageDimensions;
  basePlateThickness?: number;
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

export interface FilamentPreviewResponse {
  image: string;
  colorMatrix: ColorMatrixEntry[];
  stats: { colorCount: number; combinationCount: number };
  imageDimensions: { width: number; height: number };
  warnings: string[];
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
  basePlateThickness: number;
  doubleSided: boolean;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  detailSize?: number;
}

// Palette library types

export interface PaletteColorInfo {
  name: string;
  hex: string;
  transmission_distance: number;
}

export interface PaletteInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  colors: PaletteColorInfo[];
}

export interface PaletteLibraryResponse {
  palettes: PaletteInfo[];
  categories: Record<string, string>;
}

// Default presets for frontend initialization
export const DEFAULT_PRESETS: Record<FilamentPreset, FilamentColorConfig[]> = {
  bambu_cmyk: [
    { name: 'Cyan', hex: '#0086D6', transmission_distance: 3.0 },
    { name: 'Magenta', hex: '#EC008C', transmission_distance: 1.9 },
    { name: 'Yellow', hex: '#F4EE2A', transmission_distance: 2.5 },
    { name: 'White', hex: '#FFFFFF', transmission_distance: 7.2 },
  ],
  clear_cmyk: [
    { name: 'Cyan', hex: '#0089cd', transmission_distance: 60.0 },
    { name: 'Magenta', hex: '#e75d4a', transmission_distance: 100.0 },
    { name: 'Yellow', hex: '#f6d449', transmission_distance: 70.0 },
    { name: 'White', hex: '#FFFFFF', transmission_distance: 200.0 },
  ],
};
