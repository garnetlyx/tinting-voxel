/**
 * API client for backend communication
 */
import type {
  ProcessImageResponse,
  ProcessImageParams,
  ColorBlock,
  DownloadSTLParams
} from './types';

const API_BASE_URL = '/api';

/**
 * Process uploaded image to extract color blocks
 */
export async function processImage(
  file: File,
  params: ProcessImageParams
): Promise<ProcessImageResponse> {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('maxColors', params.maxColors.toString());
  formData.append('colorThreshold', params.colorThreshold.toString());
  formData.append('pixelSize', params.pixelSize.toString());

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

  // Download file
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'colors.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Download STL ZIP file
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

  // Download file
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'all_color_blocks.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}
