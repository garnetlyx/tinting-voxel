/**
 * API client for backend communication
 */
import type {
  ProcessImageResponse,
  SVGProcessImageResponse,
  ProcessImageParams,
  ColorBlock,
  DownloadSTLParams,
  DownloadSVGSTLParams,
} from './types';

const API_BASE_URL = '/api';

/**
 * Process uploaded image to extract color blocks (pixel mode) or vector contours (SVG mode)
 */
export async function processImage(
  file: File,
  params: ProcessImageParams
): Promise<ProcessImageResponse | SVGProcessImageResponse> {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('mode', params.mode);
  formData.append('pixelSize', params.pixelSize.toString());

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
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process image');
  }

  return response.json();
}

/**
 * Download CSV file with color data
 */
export async function downloadCSV(colorBlocks: ColorBlock[]): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/download-csv`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ colorBlocks }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to download CSV');
  }

  downloadBlobAsFile(await response.blob(), 'colors.csv');
}

/**
 * Download STL ZIP file (pixel mode)
 */
export async function downloadSTL(params: DownloadSTLParams): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/download-stl`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to download STL');
  }

  downloadBlobAsFile(await response.blob(), 'all_color_blocks.zip');
}

/**
 * Download STL ZIP file (SVG mode)
 */
export async function downloadSVGSTL(params: DownloadSVGSTLParams): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/download-svg-stl`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to download STL');
  }

  downloadBlobAsFile(await response.blob(), 'all_color_blocks.zip');
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
  setTimeout(() => URL.revokeObjectURL(url), 100);
}
