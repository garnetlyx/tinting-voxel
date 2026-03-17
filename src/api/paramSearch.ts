/**
 * API client for parameter search optimization.
 */

const API_BASE_URL = '/api';

export interface ParamSearchConfig {
  targetLongestEdgeMm: number;
  preset: string;
  mode: 'pixel' | 'svg' | 'both';
  layerCount: number;
  strategy?: 'grid' | 'random';
  nTrials?: number;
  seed?: number;
  topN?: number;
}

export interface SearchResultItem {
  rank: number;
  mode: string;
  params: Record<string, number>;
  mae: number;
  previewImage: string; // data URL
}

export interface ParamSearchResponse {
  jobId: string;
  results: SearchResultItem[];
  totalEvaluated: number;
  elapsedSeconds: number;
}

export interface ParamSearchProgress {
  jobId: string;
  completed: number;
  total: number;
  bestMae: number;
  status: 'running' | 'complete' | 'error';
  error?: string;
}

/**
 * Start a parameter search run.
 * pixel_size is derived as targetLongestEdgeMm / max(width, height).
 */
export async function startParamSearch(
  imageFile: File,
  config: ParamSearchConfig,
  imageDimensions: { width: number; height: number },
  signal?: AbortSignal,
): Promise<ParamSearchResponse> {
  const longestPx = Math.max(imageDimensions.width, imageDimensions.height);
  const pixelSize = config.targetLongestEdgeMm / longestPx;

  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('preset', config.preset);
  formData.append('mode', config.mode);
  formData.append('layer_count', config.layerCount.toString());
  formData.append('pixel_size', pixelSize.toString());
  formData.append('strategy', config.strategy ?? 'grid');
  if (config.nTrials !== undefined) formData.append('n_trials', config.nTrials.toString());
  if (config.seed !== undefined) formData.append('seed', config.seed.toString());
  if (config.topN !== undefined) formData.append('top_n', config.topN.toString());

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
    throw new Error(detail);
  }

  const raw = await response.json();
  return {
    jobId: raw.job_id,
    results: raw.results.map((r: {
      rank: number; mode: string; params: Record<string, number>;
      mae: number; preview_image: string;
    }) => ({
      rank: r.rank,
      mode: r.mode,
      params: r.params,
      mae: r.mae,
      previewImage: r.preview_image,
    })),
    totalEvaluated: raw.total_evaluated,
    elapsedSeconds: raw.elapsed_seconds,
  };
}

/**
 * Subscribe to SSE progress events for a running search job.
 * Returns a cleanup function to close the connection.
 */
export function subscribeToProgress(
  jobId: string,
  onEvent: (event: ParamSearchProgress) => void,
  onComplete: () => void,
  onError: (err: Error) => void,
): () => void {
  const es = new EventSource(`${API_BASE_URL}/param-search/progress/${jobId}`);

  es.onmessage = (e) => {
    try {
      const raw = JSON.parse(e.data);
      const event: ParamSearchProgress = {
        jobId: raw.job_id,
        completed: raw.completed,
        total: raw.total,
        bestMae: raw.best_mae,
        status: raw.status,
        error: raw.error,
      };
      onEvent(event);
      if (event.status === 'complete') {
        es.close();
        onComplete();
      } else if (event.status === 'error') {
        es.close();
        onError(new Error(event.error ?? 'Search failed'));
      }
    } catch (err) {
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  es.onerror = () => {
    es.close();
    onError(new Error('SSE connection error'));
  };

  return () => es.close();
}
