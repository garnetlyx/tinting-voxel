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
  processedImage: string;  // simulated printable image
  segmentationImage: string;  // quantized/merged source preview
  mappedBlockColors: MappedBlockColor[];
  mappedBlendPalette: MappedBlendPaletteEntry[];
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
  layerHeight?: number;
  layerCount?: number;
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

export type FilamentPreset = 'bambu_cmyk' | 'bambu_cmyk_calibrated' | 'clear_cmyk';

export interface FilamentColorConfig {
  name: string;
  hex: string;
  transmission_distance: number;
  alpha?: number;
  k?: number;
  td_scale?: number;
  td_gamma?: number;
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
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
}

export interface SimulatedPrintPreviewResponse {
  processedImage: string;
  mappedBlockColors: MappedBlockColor[];
  mappedBlendPalette: MappedBlendPaletteEntry[];
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
    { name: 'Cyan', hex: '#3D79C6', transmission_distance: 3.0 },
    { name: 'Magenta', hex: '#B3356E', transmission_distance: 1.9 },
    { name: 'Yellow', hex: '#FFE665', transmission_distance: 2.5 },
    { name: 'White', hex: '#FFFFFF', transmission_distance: 7.2 },
  ],
  bambu_cmyk_calibrated: [
    {
      name: 'Cyan',
      hex: '#3D79C6',
      transmission_distance: 2.0,
      alpha: 5.751822945330163,
      k: 1.2085100532667932,
      td_scale: 1.0056869820712098,
      td_gamma: 0.4543363851088494,
    },
    {
      name: 'Magenta',
      hex: '#B3356E',
      transmission_distance: 2.9,
      alpha: 5.751822945330163,
      k: 0.35481383708372416,
      td_scale: 1.0056869820712098,
      td_gamma: 0.4543363851088494,
    },
    {
      name: 'Yellow',
      hex: '#FFE665',
      transmission_distance: 5.0,
      alpha: 5.751822945330163,
      k: 8.401071443503248,
      td_scale: 1.0056869820712098,
      td_gamma: 0.4543363851088494,
    },
    {
      name: 'White',
      hex: '#FFFFFF',
      transmission_distance: 6.1,
      alpha: 5.751822945330163,
      k: 6.523686193460801,
      td_scale: 1.0056869820712098,
      td_gamma: 0.4543363851088494,
    },
    {
      name: 'Key',
      hex: '#0B0F0C',
      transmission_distance: 0.1,
      alpha: 5.751822945330163,
      k: 5.440433103311526,
      td_scale: 1.0056869820712098,
      td_gamma: 0.4543363851088494,
    },
  ],
  clear_cmyk: [
    { name: 'Cyan', hex: '#0089cd', transmission_distance: 60.0 },
    { name: 'Magenta', hex: '#e75d4a', transmission_distance: 100.0 },
    { name: 'Yellow', hex: '#f6d449', transmission_distance: 70.0 },
    { name: 'White', hex: '#FFFFFF', transmission_distance: 200.0 },
  ],
};
