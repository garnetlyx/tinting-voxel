/**
 * Tests for the param-search API client: the FormData payload must carry the
 * full current print configuration (layer height, backing, current mode
 * params) — a regression guard for the white-preview bug where the search ran
 * at the backend default layer height instead of the user's.
 */
import { describe, expect, it, vi } from 'vitest';
import { cancelParamSearch, getParamSearchProgress, startParamSearch } from './paramSearch';
import type { FilamentColorConfig } from './types';

const colors: FilamentColorConfig[] = [
  { name: 'Cyan', hex: '#00FFFF', transmission_distance: 4.7 },
  { name: 'Magenta', hex: '#FF00FF', transmission_distance: 6.3 },
  { name: 'Yellow', hex: '#FFFF00', transmission_distance: 10.1 },
  { name: 'Green', hex: '#00FF00', transmission_distance: 5.0 },
];

function lastFormData(): FormData {
  const call = vi.mocked(fetch).mock.calls[0];
  return call?.[1]?.body as FormData;
}

describe('startParamSearch', () => {
  it('sends the current stack and mode params to the backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: 'job-1',
        completed: 0,
        total: 21,
        status: 'running',
        results: [],
      }),
    }));

    await startParamSearch(
      new File(['x'], 'img.png', { type: 'image/png' }),
      {
        targetLongestEdgeMm: 200,
        filamentColors: colors,
        mode: 'pixel',
        layerCount: 8,
        layerHeight: 0.84,
        whiteBackingLayers: 0,
        maxColors: 50,
        colorThreshold: 35,
        detailSize: 0.42,
        numColors: 8,
        epsilon: 2,
        minArea: 4,
      },
      { width: 896, height: 1344 },
    );

    const form = lastFormData();
    expect(form.get('layer_height')).toBe('0.84');
    expect(form.get('white_backing_layers')).toBe('0');
    expect(form.get('layer_count')).toBe('8');
    expect(form.get('max_colors')).toBe('50');
    expect(form.get('color_threshold')).toBe('35');
    expect(form.get('detail_size')).toBe('0.42');
    expect(form.get('num_colors')).toBe('8');
    expect(form.get('epsilon')).toBe('2');
    expect(form.get('min_area')).toBe('4');
    // pixel_size derived from the target physical size
    expect(Number(form.get('pixel_size'))).toBeCloseTo(200 / 1344, 6);
    expect(form.get('filamentColors')).toBe(JSON.stringify(colors));
    // The server owns the search strategy and its trial budget.
    expect(form.get('strategy')).toBeNull();
    expect(form.get('n_trials')).toBeNull();
  });

  it('throws the backend detail on error responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'boom' }),
    }));

    await expect(
      startParamSearch(
        new File(['x'], 'img.png', { type: 'image/png' }),
        {
          targetLongestEdgeMm: 100,
          mode: 'pixel',
          layerCount: 4,
          layerHeight: 0.08,
          whiteBackingLayers: 1,
          maxColors: 10,
          colorThreshold: 50,
          detailSize: 0.42,
          numColors: 8,
          epsilon: 2,
          minArea: 4,
        },
        { width: 100, height: 100 },
      ),
    ).rejects.toThrow('boom');
  });

  it('polls only new completed previews and can cancel the job', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job_id: 'job-1', completed: 2, total: 21, status: 'running', error: null,
        results: [{ candidate_id: 2, is_baseline: false, mode: 'pixel',
          params: { detail_size: 0.42 }, preview_image: 'data:image/png;base64,abc', score: 8.85 }],
      }),
    }).mockResolvedValueOnce({ ok: true }));

    const progress = await getParamSearchProgress('job-1', 1);
    expect(progress.completed).toBe(2);
    expect(progress.results[0].candidateId).toBe(2);
    expect(progress.results[0].score).toBe(8.85);
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/api/param-search/progress/job-1?after=1');

    await cancelParamSearch('job-1');
    expect(vi.mocked(fetch).mock.calls[1][1]).toEqual({ method: 'DELETE' });
  });

  it('does not report a failed cancellation as success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }));
    await expect(cancelParamSearch('job-1')).rejects.toThrow('Failed to cancel search');
  });
});
