/**
 * API client for backend communication
 */
import { runHeavy } from './heavyJob';
import { getErrorDetail } from './errors';
import { withLabelMap } from '../utils/labelMap';
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
  FilamentSetInfo,
  FilamentPreviewResponse,
  SimulatedPrintPreviewParams,
  SimulatedPrintPreviewResponse,
  BatchProcessResponse,
  BatchProcessParams,
  BatchDownloadSTLParams,
  PaletteLibraryResponse,
  HeavyCallOptions,
} from './types';

const API_BASE_URL = '/api';


/**
 * Process uploaded image to extract color blocks (pixel mode) or vector contours (SVG mode)
 */
export async function processImage(
  file: File,
  params: ProcessImageParams,
  opts: HeavyCallOptions = {},
): Promise<ProcessImageResponse | SVGProcessImageResponse> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('mode', effective.mode);
    formData.append('pixelSize', effective.pixelSize.toString());
    if (effective.layerHeight !== undefined) formData.append('layerHeight', effective.layerHeight.toString());
    if (effective.layerCount !== undefined) formData.append('layerCount', effective.layerCount.toString());
    if (effective.whiteBackingLayers !== undefined) formData.append('whiteBackingLayers', effective.whiteBackingLayers.toString());
    if (effective.backingFilament !== undefined) formData.append('backingFilament', effective.backingFilament);
    if (forced) formData.append('forceOversize', 'true');

    if (effective.filamentPreset) {
      formData.append('filamentPreset', effective.filamentPreset);
    } else if (effective.filamentColors) {
      formData.append('filamentColors', JSON.stringify(effective.filamentColors));
    }

    if (effective.detailSize !== undefined) {
      formData.append('detailSize', effective.detailSize.toString());
    }

    if (effective.mode === 'pixel' && effective.pixelParams) {
      formData.append('maxColors', effective.pixelParams.maxColors.toString());
      formData.append('colorThreshold', effective.pixelParams.colorThreshold.toString());
    } else if (effective.mode === 'svg' && effective.svgParams) {
      formData.append('epsilon', effective.svgParams.epsilon.toString());
      formData.append('minArea', effective.svgParams.minArea.toString());
      formData.append('numColors', effective.svgParams.numColors.toString());
    }

    return fetch(`${API_BASE_URL}/process-image`, {
      method: 'POST',
      body: formData,
      signal: opts.signal,
    });
  };

  return runHeavy(
    submit,
    response => response.json(),
    opts,
    suggestion => {
      effective = {
        ...effective,
        pixelSize: suggestion.pixelSize ?? effective.pixelSize,
        layerCount: suggestion.layerCount ?? effective.layerCount,
      };
    },
    'Failed to process image',
  );
}

/**
 * Recompute simulated print preview for current color blocks and filament setup.
 */
export async function simulatePrintPreview(
  params: SimulatedPrintPreviewParams,
  opts: HeavyCallOptions = {},
): Promise<SimulatedPrintPreviewResponse> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => fetch(`${API_BASE_URL}/simulate-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(withLabelMap({ ...effective, forceOversize: forced })),
    signal: opts.signal,
  });
  return runHeavy(
    submit,
    response => response.json(),
    opts,
    suggestion => {
      effective = { ...effective, layerCount: suggestion.layerCount ?? effective.layerCount };
    },
    'Failed to simulate print preview',
  );
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
    body: JSON.stringify({ colorBlocks: colorBlocks.map(({ r, g, b, hex, count }) => ({ r, g, b, hex, count })) }),
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
export async function downloadSTLV2(params: DownloadSTLParamsV2, opts: HeavyCallOptions = {}): Promise<void> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => fetch(`${API_V2_BASE_URL}/download-stl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(withLabelMap({ ...effective, forceOversize: forced })),
    signal: opts.signal,
  });
  await runHeavy(
    submit,
    async response => { downloadBlobAsFile(await response.blob(), 'all_color_blocks.zip'); },
    opts,
    suggestion => {
      effective = { ...effective, layerCount: suggestion.layerCount ?? effective.layerCount };
    },
    'Failed to download STL',
  );
}

/**
 * What a filament set supports: the most color layers the backend can search
 * within its time limit, and the backing filament used unless one is chosen.
 */
export async function getFilamentSet(
  filament: Pick<FilamentPreviewParams, 'filamentPreset' | 'filamentColors'>,
  signal?: AbortSignal,
): Promise<FilamentSetInfo> {
  const response = await fetch(`${API_V2_BASE_URL}/filament-set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(filament),
    signal,
  });
  if (!response.ok) {
    throw new Error(await getErrorDetail(response, 'Failed to describe the filament set'));
  }
  return response.json();
}

/**
 * Get filament color preview (color matrix image and stats)
 */
export async function getFilamentPreview(
  params: FilamentPreviewParams,
  opts: HeavyCallOptions = {},
): Promise<FilamentPreviewResponse> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => fetch(`${API_BASE_URL}/filament-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...effective, forceOversize: forced }),
    signal: opts.signal,
  });
  return runHeavy(
    submit,
    response => response.json(),
    opts,
    suggestion => {
      effective = {
        ...effective,
        layerCount: suggestion.layerCount ?? effective.layerCount,
        ...(suggestion.pageSize !== undefined ? { page: 1, pageSize: suggestion.pageSize } : {}),
      };
    },
    'Failed to get filament preview',
  );
}

/**
 * Download STL ZIP file with configurable colors (SVG mode, V2 API)
 */
export async function downloadSVGSTLV2(params: DownloadSVGSTLParamsV2, opts: HeavyCallOptions = {}): Promise<void> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => fetch(`${API_V2_BASE_URL}/download-svg-stl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...effective, forceOversize: forced }),
    signal: opts.signal,
  });
  await runHeavy(
    submit,
    async response => { downloadBlobAsFile(await response.blob(), 'all_color_blocks.zip'); },
    opts,
    suggestion => {
      effective = { ...effective, layerCount: suggestion.layerCount ?? effective.layerCount };
    },
    'Failed to download STL',
  );
}

/**
 * Download 3MF file with color-separated objects (V2 API, pixel mode)
 */
export async function download3MFV2(params: DownloadSTLParamsV2, opts: HeavyCallOptions = {}): Promise<void> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => fetch(`${API_V2_BASE_URL}/download-3mf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(withLabelMap({ ...effective, forceOversize: forced })),
    signal: opts.signal,
  });
  await runHeavy(
    submit,
    async response => { downloadBlobAsFile(await response.blob(), 'color_blocks.3mf'); },
    opts,
    suggestion => {
      effective = { ...effective, layerCount: suggestion.layerCount ?? effective.layerCount };
    },
    'Failed to download 3MF',
  );
}

/**
 * Download 3MF file from SVG vector contours (V2 API, SVG mode)
 */
export async function downloadSVG3MFV2(params: DownloadSVGSTLParamsV2, opts: HeavyCallOptions = {}): Promise<void> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => fetch(`${API_V2_BASE_URL}/download-svg-3mf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...effective, forceOversize: forced }),
    signal: opts.signal,
  });
  await runHeavy(
    submit,
    async response => { downloadBlobAsFile(await response.blob(), 'color_blocks.3mf'); },
    opts,
    suggestion => {
      effective = { ...effective, layerCount: suggestion.layerCount ?? effective.layerCount };
    },
    'Failed to download 3MF',
  );
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
  opts: HeavyCallOptions = {},
): Promise<BatchProcessResponse> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('images', file);
    }
    formData.append('maxColors', effective.maxColors.toString());
    formData.append('colorThreshold', effective.colorThreshold.toString());
    formData.append('pixelSize', effective.pixelSize.toString());
    if (forced) formData.append('forceOversize', 'true');

    if (effective.detailSize !== undefined) {
      formData.append('detailSize', effective.detailSize.toString());
    }

    return fetch(`${API_BATCH_BASE_URL}/process`, {
      method: 'POST',
      body: formData,
      signal: opts.signal,
    });
  };
  return runHeavy(
    submit,
    response => response.json(),
    opts,
    suggestion => {
      effective = { ...effective, pixelSize: suggestion.pixelSize ?? effective.pixelSize };
    },
    'Failed to process batch',
  );
}

/**
 * Download STL ZIPs for multiple images in batch mode
 */
export async function batchDownloadSTL(
  files: File[],
  params: BatchDownloadSTLParams,
  opts: HeavyCallOptions = {},
): Promise<void> {
  let effective = params;
  const submit = (forced: boolean): Promise<Response> => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('images', file);
    }
    formData.append('maxColors', effective.maxColors.toString());
    formData.append('colorThreshold', effective.colorThreshold.toString());
    formData.append('pixelSize', effective.pixelSize.toString());
    formData.append('layerHeight', effective.layerHeight.toString());
    formData.append('layerCount', effective.layerCount.toString());
    formData.append('whiteBackingLayers', effective.whiteBackingLayers.toString());
    if (forced) formData.append('forceOversize', 'true');
    if (effective.backingFilament !== undefined) formData.append('backingFilament', effective.backingFilament);
    if (effective.filamentPreset) {
      formData.append('filamentPreset', effective.filamentPreset);
    }
    if (effective.filamentColors && effective.filamentColors.length > 0) {
      formData.append('filamentColors', JSON.stringify(effective.filamentColors));
    }
    if (effective.detailSize !== undefined) {
      formData.append('detailSize', effective.detailSize.toString());
    }

    return fetch(`${API_BATCH_BASE_URL}/download-stl`, {
      method: 'POST',
      body: formData,
      signal: opts.signal,
    });
  };
  await runHeavy(
    submit,
    async response => { downloadBlobAsFile(await response.blob(), 'batch_stl_output.zip'); },
    opts,
    suggestion => {
      effective = {
        ...effective,
        pixelSize: suggestion.pixelSize ?? effective.pixelSize,
        layerCount: suggestion.layerCount ?? effective.layerCount,
      };
    },
    'Failed to download batch STL',
  );
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
