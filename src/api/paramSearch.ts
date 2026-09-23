/**
 * API client for parameter search optimization.
 */

import type { FilamentColorConfig } from './types';

const API_BASE_URL = '/api';
export const MAX_SEARCH_PIXEL_SIZE_MM = 10;
export const MAX_SEARCH_TARGET_EDGE_MM = 500;

export interface ImageDimensions { width: number; height: number }

export function maxSearchTargetEdgeMm(imageDimensions: ImageDimensions): number {
  const longestPx = Math.max(imageDimensions.width, imageDimensions.height);
  if (!Number.isFinite(longestPx) || longestPx <= 0) return 0;
  return Math.min(MAX_SEARCH_TARGET_EDGE_MM, MAX_SEARCH_PIXEL_SIZE_MM * longestPx);
}

export function isValidSearchTargetEdgeMm(targetMm: number, imageDimensions: ImageDimensions): boolean {
  const maxMm = maxSearchTargetEdgeMm(imageDimensions);
  return Number.isFinite(targetMm) && targetMm > 0 && maxMm > 0 && targetMm <= maxMm;
}

export interface ParamSearchConfig {
  targetLongestEdgeMm: number;
  /** Current filament configuration; either a named preset or custom colors. */
  preset?: string;
  filamentColors?: FilamentColorConfig[];
  mode: 'pixel' | 'svg' | 'both';
  layerCount: number;
  layerHeight: number;
  whiteBackingLayers: number;
  backingMode?: 'white' | 'black';
  maxColors: number;
  colorThreshold: number;
  detailSize: number;
  numColors: number;
  epsilon: number;
  minArea: number;
  strategy?: 'grid' | 'random';
  nTrials?: number;
  seed?: number;
}

export interface SearchResultItem {
  candidateId: number;
  isBaseline: boolean;
  mode: string;
  params: Record<string, number>;
  previewImage: string; // data URL
}

export interface ParamSearchResponse {
  jobId: string;
  completed: number;
  total: number;
  status: 'running' | 'complete' | 'cancelled' | 'error';
  settled: boolean;
}

export interface ParamSearchProgress {
  jobId: string;
  completed: number;
  total: number;
  status: 'running' | 'complete' | 'cancelled' | 'error';
  settled: boolean;
  error?: string;
  results: SearchResultItem[];
}

export class ParamSearchHttpError extends Error {
  constructor(message: string, readonly status: number, readonly retryAfterMs?: number) {
    super(message);
  }
}

function retryAfterMs(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  const delay = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(value) - Date.now();
  return Number.isFinite(delay) && delay > 0 ? delay : undefined;
}

function parseResult(raw: {
  candidate_id: number; is_baseline: boolean; mode: string;
  params: Record<string, number>; preview_image: string;
}): SearchResultItem {
  return {
    candidateId: raw.candidate_id,
    isBaseline: raw.is_baseline,
    mode: raw.mode,
    params: raw.params,
    previewImage: raw.preview_image,
  };
}

/**
 * Start a parameter search run.
 * pixel_size is derived as targetLongestEdgeMm / max(width, height).
 */
export async function startParamSearch(
  imageFile: File,
  config: ParamSearchConfig,
  imageDimensions: ImageDimensions,
  signal?: AbortSignal,
): Promise<ParamSearchResponse> {
  if (!isValidSearchTargetEdgeMm(config.targetLongestEdgeMm, imageDimensions)) {
    throw new Error(`Target edge must be greater than 0 and no more than ${maxSearchTargetEdgeMm(imageDimensions)} mm for this image.`);
  }
  const longestPx = Math.max(imageDimensions.width, imageDimensions.height);
  const pixelSize = config.targetLongestEdgeMm / longestPx;

  const formData = new FormData();
  formData.append('image', imageFile);
  if (config.filamentColors?.length) {
    formData.append('filamentColors', JSON.stringify(config.filamentColors));
  } else if (config.preset) {
    formData.append('preset', config.preset);
  }
  formData.append('mode', config.mode);
  formData.append('layer_count', config.layerCount.toString());
  formData.append('layer_height', config.layerHeight.toString());
  formData.append('white_backing_layers', config.whiteBackingLayers.toString());
  formData.append('backing_mode', config.backingMode ?? 'white');
  formData.append('max_colors', config.maxColors.toString());
  formData.append('color_threshold', config.colorThreshold.toString());
  formData.append('detail_size', config.detailSize.toString());
  formData.append('num_colors', config.numColors.toString());
  formData.append('epsilon', config.epsilon.toString());
  formData.append('min_area', config.minArea.toString());
  formData.append('pixel_size', pixelSize.toString());
  formData.append('strategy', config.strategy ?? 'grid');
  if (config.nTrials !== undefined) formData.append('n_trials', config.nTrials.toString());
  if (config.seed !== undefined) formData.append('seed', config.seed.toString());

  const response = await fetch(`${API_BASE_URL}/param-search`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    let detail = 'Failed to start parameter search';
    try {
      const body = await response.json();
      detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch { /* ignore */ }
    throw new ParamSearchHttpError(detail, response.status, retryAfterMs(response.headers?.get('Retry-After') ?? null));
  }

  const raw = await response.json();
  return {
    jobId: raw.job_id,
    completed: raw.completed,
    total: raw.total,
    status: raw.status,
    settled: raw.settled,
  };
}

export async function getParamSearchProgress(
  jobId: string,
  after: number,
): Promise<ParamSearchProgress> {
  const response = await fetch(`${API_BASE_URL}/param-search/progress/${encodeURIComponent(jobId)}?after=${after}`);
  if (!response.ok) throw new ParamSearchHttpError('Failed to read search progress', response.status);
  const raw = await response.json();
  return {
    jobId: raw.job_id,
    completed: raw.completed,
    total: raw.total,
    status: raw.status,
    settled: raw.settled,
    error: raw.error ?? undefined,
    results: raw.results.map(parseResult),
  };
}

export async function isParamSearchAvailable(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/param-search/availability`);
  if (!response.ok) throw new ParamSearchHttpError('Failed to check search availability', response.status);
  const raw = await response.json();
  return raw.available === true;
}

export async function cancelParamSearch(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/param-search/progress/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
  if (!response.ok && response.status !== 404) {
    throw new ParamSearchHttpError('Failed to cancel search', response.status);
  }
}
