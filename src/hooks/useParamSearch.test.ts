import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ParamSearchHttpError, cancelParamSearch, getParamSearchProgress, isParamSearchAvailable, startParamSearch } from '../api/paramSearch';
import { useParamSearch } from './useParamSearch';

vi.mock('../api/paramSearch', async (importOriginal) => ({
  ...await importOriginal<typeof import('../api/paramSearch')>(),
  startParamSearch: vi.fn(),
  getParamSearchProgress: vi.fn(),
  cancelParamSearch: vi.fn(),
}));

const config = {
  targetLongestEdgeMm: 200,
  mode: 'pixel' as const,
  layerCount: 4,
  layerHeight: 0.08,
  whiteBackingLayers: 3,
  maxColors: 10,
  colorThreshold: 50,
  detailSize: 0.42,
  numColors: 8,
  epsilon: 2,
  minArea: 4,
};

const firstPreview = {
  candidateId: 1,
  isBaseline: true,
  mode: 'pixel',
  params: { max_colors: 10, color_threshold: 50, detail_size: 0.42 },
  previewImage: 'data:image/png;base64,first',
};

describe('useParamSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(startParamSearch).mockResolvedValue({ jobId: 'local-photo-job', completed: 0, total: 21, status: 'running', settled: false });
    vi.mocked(cancelParamSearch).mockResolvedValue();
    vi.mocked(isParamSearchAvailable).mockResolvedValue(true);
  });

  it('keeps the first full-size preview visible while the remaining candidates run', async () => {
    vi.mocked(getParamSearchProgress)
      .mockResolvedValueOnce({ jobId: 'local-photo-job', completed: 1, total: 21, status: 'running', settled: false, results: [firstPreview] })
      .mockResolvedValueOnce({ jobId: 'local-photo-job', completed: 1, total: 21, status: 'complete', settled: true, results: [] });

    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });

    await waitFor(() => expect(result.current.results).toEqual([firstPreview]));
    expect(result.current.phase).toBe('running');
    await waitFor(() => expect(result.current.phase).toBe('results'), { timeout: 3000 });
    expect(vi.mocked(getParamSearchProgress).mock.calls.map((call) => call[1])).toEqual([0, 1]);
  });

  it('cancels the server job when the dialog closes', async () => {
    vi.mocked(getParamSearchProgress).mockImplementation(async () => ({
      jobId: 'local-photo-job', completed: 1, total: 21,
      status: vi.mocked(cancelParamSearch).mock.calls.length ? 'cancelled' : 'running',
      settled: vi.mocked(cancelParamSearch).mock.calls.length > 0,
      results: vi.mocked(cancelParamSearch).mock.calls.length ? [] : [firstPreview],
    }));

    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(result.current.results).toHaveLength(1));
    act(() => result.current.reset());
    expect(result.current.phase).toBe('waiting');
    expect(cancelParamSearch).toHaveBeenCalledWith('local-photo-job');
    await waitFor(() => expect(result.current.phase).toBe('idle'));
  });

  it('continues the same job after a temporary progress-read failure', async () => {
    vi.mocked(getParamSearchProgress)
      .mockResolvedValueOnce({ jobId: 'local-photo-job', completed: 1, total: 2, status: 'running', settled: false, results: [firstPreview] })
      .mockRejectedValueOnce(new Error('Failed to fetch'))
      .mockResolvedValueOnce({ jobId: 'local-photo-job', completed: 2, total: 2, status: 'complete', settled: true, results: [{ ...firstPreview, candidateId: 2, isBaseline: false }] });

    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(result.current.results).toHaveLength(2), { timeout: 5000 });
    expect(result.current.phase).toBe('results');
    expect(cancelParamSearch).not.toHaveBeenCalled();
    expect(vi.mocked(getParamSearchProgress).mock.calls.map((call) => call[1])).toEqual([0, 1, 1]);
  });

  it('retries a temporary cancellation failure after closing', async () => {
    vi.mocked(getParamSearchProgress).mockImplementation(async () => ({
      jobId: 'local-photo-job', completed: 1, total: 21,
      status: vi.mocked(cancelParamSearch).mock.calls.length > 1 ? 'cancelled' : 'running',
      settled: vi.mocked(cancelParamSearch).mock.calls.length > 1,
      results: vi.mocked(cancelParamSearch).mock.calls.length > 1 ? [] : [firstPreview],
    }));
    vi.mocked(cancelParamSearch).mockRejectedValueOnce(new Error('Failed to fetch')).mockResolvedValueOnce();

    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(result.current.results).toHaveLength(1));
    act(() => result.current.reset());
    await waitFor(() => expect(cancelParamSearch).toHaveBeenCalledTimes(2), { timeout: 3000 });
    await waitFor(() => expect(result.current.phase).toBe('idle'));
  });

  it('keeps restart waiting until the cancelled worker releases its slot', async () => {
    let released = false;
    vi.mocked(startParamSearch)
      .mockResolvedValueOnce({ jobId: 'first-job', completed: 0, total: 2, status: 'running', settled: false })
      .mockResolvedValueOnce({ jobId: 'second-job', completed: 0, total: 2, status: 'running', settled: false });
    vi.mocked(getParamSearchProgress).mockImplementation(async (jobId) => {
      if (jobId === 'first-job') return {
        jobId, completed: 0, total: 2, status: vi.mocked(cancelParamSearch).mock.calls.length ? 'cancelled' : 'running',
        settled: released, results: [],
      };
      return { jobId, completed: 1, total: 1, status: 'complete', settled: true, results: [firstPreview] };
    });

    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(startParamSearch).toHaveBeenCalledTimes(1));
    act(() => { result.current.reset(); result.current.openConfig(); });
    expect(result.current.phase).toBe('waiting');
    expect(startParamSearch).toHaveBeenCalledTimes(1);
    released = true;
    await waitFor(() => expect(result.current.phase).toBe('idle'), { timeout: 3000 });
    act(() => { result.current.openConfig(); void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(startParamSearch).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(result.current.phase).toBe('results'));
  });

  it('automatically retries a 429 after the server Retry-After delay', async () => {
    vi.mocked(startParamSearch)
      .mockRejectedValueOnce(new ParamSearchHttpError('Rate limit exceeded', 429, 1))
      .mockResolvedValueOnce({ jobId: 'next-job', completed: 0, total: 1, status: 'running', settled: false });
    vi.mocked(getParamSearchProgress).mockResolvedValue({
      jobId: 'next-job', completed: 1, total: 1, status: 'complete', settled: true, results: [firstPreview],
    });
    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(result.current.phase).toBe('waiting'));
    await waitFor(() => expect(result.current.phase).toBe('results'));
    expect(startParamSearch).toHaveBeenCalledTimes(2);
  });

  it('waits for availability after 503 before retrying POST', async () => {
    vi.mocked(startParamSearch)
      .mockRejectedValueOnce(new ParamSearchHttpError('Search already running', 503))
      .mockResolvedValueOnce({ jobId: 'next-job', completed: 0, total: 1, status: 'running', settled: false });
    vi.mocked(isParamSearchAvailable).mockResolvedValueOnce(true);
    vi.mocked(getParamSearchProgress).mockResolvedValue({
      jobId: 'next-job', completed: 1, total: 1, status: 'complete', settled: true, results: [firstPreview],
    });
    const { result } = renderHook(() => useParamSearch());
    act(() => { void result.current.startSearch(new File(['x'], 'local-photo.JPG'), config, { width: 953, height: 1270 }); });
    await waitFor(() => expect(result.current.phase).toBe('results'));
    expect(isParamSearchAvailable).toHaveBeenCalledOnce();
    expect(startParamSearch).toHaveBeenCalledTimes(2);
  });
});
