/**
 * API client for backend communication
 */
import { recordBugReportLog } from '../utils/bugReport';
import type {
  BugReportRequest,
  BugReportResponse,
  ProcessImageResponse,
  SVGProcessImageResponse,
  ProcessImageParams,
  ColorBlock,
  DownloadSTLParamsV2,
  DownloadSVGSTLParamsV2,
  PrintSettingsParams,
  FilamentPresetsResponse,
  FilamentPreviewParams,
  FilamentPreviewResponse,
  SimulatedPrintPreviewParams,
  SimulatedPrintPreviewResponse,
  BatchProcessResponse,
  BatchProcessParams,
  BatchDownloadSTLParams,
  PaletteLibraryResponse,
} from './types';

const API_BASE_URL = '/api';

/**
 * Safely extract error detail from a response that may not be JSON
 * FastAPI validation errors return detail as an array of objects
 */
async function getErrorDetail(response: Response, fallback: string): Promise<string> {
  recordBugReportLog('error', `API request failed (${response.status}): ${response.url || fallback}`);
  try {
    const body = await response.json();
    const detail = body.detail;

    // FastAPI validation errors return detail as an array: [{type, loc, msg, ...}]
    if (Array.isArray(detail)) {
      // Extract the first error message, or join all messages
      const messages = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).filter(Boolean);
      return messages.length > 0 ? messages.join('; ') : fallback;
    }

    // String detail
    if (typeof detail === 'string') {
      return detail;
    }

    return fallback;
  } catch {
    return fallback;
  }
}

/**
 * Process uploaded image to extract color blocks (pixel mode) or vector contours (SVG mode)
 */
export async function processImage(
  file: File,
  params: ProcessImageParams,
  signal?: AbortSignal
): Promise<ProcessImageResponse | SVGProcessImageResponse> {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('mode', params.mode);
  formData.append('pixelSize', params.pixelSize.toString());
  if (params.layerHeight !== undefined) formData.append('layerHeight', params.layerHeight.toString());
  if (params.layerCount !== undefined) formData.append('layerCount', params.layerCount.toString());
  if (params.whiteBackingLayers !== undefined) formData.append('whiteBackingLayers', params.whiteBackingLayers.toString());
  if (params.backingMode !== undefined) formData.append('backingMode', params.backingMode);

  if (params.filamentPreset) {
    formData.append('filamentPreset', params.filamentPreset);
  } else if (params.filamentColors) {
    formData.append('filamentColors', JSON.stringify(params.filamentColors));
  }

  if (params.detailSize !== undefined) {
    formData.append('detailSize', params.detailSize.toString());
  }

  if (params.targetWidth !== undefined) {
    formData.append('targetWidth', params.targetWidth.toString());
  }

  if (params.mode === 'pixel' && params.pixelParams) {
    formData.append('maxColors', params.pixelParams.maxColors.toString());
    formData.append('colorThreshold', params.pixelParams.colorThreshold.toString());
  } else if (params.mode === 'svg' && params.svgParams) {
    formData.append('epsilon', params.svgParams.epsilon.toString());
    formData.append('minArea', params.svgParams.minArea.toString());
    formData.append('numColors', params.svgParams.numColors.toString());
  }

  const response = await fetch(`${API_BASE_URL}/process-image`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to process image'));
  }

  return response.json();
}

/**
 * Recompute simulated print preview for current color blocks and filament setup.
 */
export async function simulatePrintPreview(
  params: SimulatedPrintPreviewParams,
  signal?: AbortSignal
): Promise<SimulatedPrintPreviewResponse> {
  const response = await fetch(`${API_BASE_URL}/simulate-preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to simulate print preview'));
  }

  return response.json();
}

/**
 * Download CSV file with color data
 */
export async function downloadCSV(colorBlocks: ColorBlock[], signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/download-csv`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ colorBlocks }),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download CSV'));
  }

  downloadBlobAsFile(await response.blob(), 'colors.csv');
}

/**
 * Helper to download a blob as a file
 */
function downloadBlobAsFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// V2 API endpoints with configurable filament colors

const API_V2_BASE_URL = '/api/v2';

/**
 * Get available filament presets
 */
export async function getFilamentPresets(signal?: AbortSignal): Promise<FilamentPresetsResponse> {
  const response = await fetch(`${API_V2_BASE_URL}/filament-presets`, {
    method: 'GET',
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to get filament presets'));
  }

  return response.json();
}

/**
 * Download STL ZIP file with configurable colors (V2 API)
 */
export async function downloadSTLV2(params: DownloadSTLParamsV2, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_V2_BASE_URL}/download-stl`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download STL'));
  }

  downloadBlobAsFile(await response.blob(), 'all_color_blocks.zip');
}

/**
 * Get filament color preview (color matrix image and stats)
 */
export async function getFilamentPreview(
  params: FilamentPreviewParams,
  signal?: AbortSignal
): Promise<FilamentPreviewResponse> {
  const response = await fetch(`${API_BASE_URL}/filament-preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to get filament preview'));
  }

  return response.json();
}

/**
 * Download STL ZIP file with configurable colors (SVG mode, V2 API)
 */
export async function downloadSVGSTLV2(params: DownloadSVGSTLParamsV2, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_V2_BASE_URL}/download-svg-stl`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download STL'));
  }

  downloadBlobAsFile(await response.blob(), 'all_color_blocks.zip');
}

/**
 * Download 3MF file with color-separated objects (V2 API, pixel mode)
 */
export async function download3MFV2(params: DownloadSTLParamsV2, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_V2_BASE_URL}/download-3mf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download 3MF'));
  }

  downloadBlobAsFile(await response.blob(), 'color_blocks.3mf');
}

/**
 * Download 3MF file from SVG vector contours (V2 API, SVG mode)
 */
export async function downloadSVG3MFV2(params: DownloadSVGSTLParamsV2, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_V2_BASE_URL}/download-svg-3mf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download 3MF'));
  }

  downloadBlobAsFile(await response.blob(), 'color_blocks.3mf');
}

/**
 * Download print settings JSON file (V2 API)
 */
export async function downloadPrintSettings(params: PrintSettingsParams, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_V2_BASE_URL}/print-settings`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download print settings'));
  }

  downloadBlobAsFile(await response.blob(), 'print_settings.json');
}

// Batch processing endpoints

const API_BATCH_BASE_URL = '/api/batch';

/**
 * Process multiple images in batch mode
 */
export async function batchProcessImages(
  files: File[],
  params: BatchProcessParams,
  signal?: AbortSignal
): Promise<BatchProcessResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('images', file);
  }
  formData.append('maxColors', params.maxColors.toString());
  formData.append('colorThreshold', params.colorThreshold.toString());
  formData.append('pixelSize', params.pixelSize.toString());

  if (params.detailSize !== undefined) {
    formData.append('detailSize', params.detailSize.toString());
  }

  const response = await fetch(`${API_BATCH_BASE_URL}/process`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to process batch'));
  }

  return response.json();
}

/**
 * Download STL ZIPs for multiple images in batch mode
 */
export async function batchDownloadSTL(
  files: File[],
  params: BatchDownloadSTLParams,
  signal?: AbortSignal
): Promise<void> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('images', file);
  }
  formData.append('maxColors', params.maxColors.toString());
  formData.append('colorThreshold', params.colorThreshold.toString());
  formData.append('pixelSize', params.pixelSize.toString());
  formData.append('layerHeight', params.layerHeight.toString());
  formData.append('layerCount', params.layerCount.toString());
  formData.append('whiteBackingLayers', params.whiteBackingLayers.toString());
  if (params.backingMode !== undefined) formData.append('backingMode', params.backingMode);
  if (params.filamentPreset) {
    formData.append('filamentPreset', params.filamentPreset);
  }
  if (params.filamentColors && params.filamentColors.length > 0) {
    formData.append('filamentColors', JSON.stringify(params.filamentColors));
  }
  if (params.detailSize !== undefined) {
    formData.append('detailSize', params.detailSize.toString());
  }

  const response = await fetch(`${API_BATCH_BASE_URL}/download-stl`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to download batch STL'));
  }

  downloadBlobAsFile(await response.blob(), 'batch_stl_output.zip');
}

// Palette library endpoints

const API_PALETTE_BASE_URL = '/api/palettes';

/**
 * Get both supported filament palettes
 */
export async function getPaletteLibrary(
  signal?: AbortSignal
): Promise<PaletteLibraryResponse> {

  const response = await fetch(`${API_PALETTE_BASE_URL}/`, { method: 'GET', signal });

  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to load palette library'));
  }

  return response.json();
}

/** Submit feedback with a bounded timeout and actionable retry messages. */
export async function submitBugReport(body: BugReportRequest, signal?: AbortSignal): Promise<BugReportResponse> {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = window.setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(`${API_BASE_URL}/bug-report`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: controller.signal,
    });
    if (response.status === 429) throw new Error('Too many reports. Please try again in an hour.');
    if (!response.ok) throw new Error(await getErrorDetail(response, 'Could not send your report. Please try again.'));
    const result: BugReportResponse = await response.json();
    if (result.success !== true || typeof result.reportId !== 'string' || !result.reportId) {
      throw new Error('The server did not confirm your report. Please try again.');
    }
    return result;
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('Sending timed out. Please try again.');
    throw error;
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}
