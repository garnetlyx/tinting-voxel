/**
 * Tests for the queue-aware heavy-job wrapper (src/api/heavyJob.ts).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { runHeavy } from './heavyJob';
import { heavyQueue } from '../utils/heavyQueueStore';
import type { OversizeChoice } from './types';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const OVERSIZE_DETAIL = {
  code: 'job_too_large',
  message: 'This job is estimated to need 4.0 GB of memory.',
  estimatedMb: 4096,
  budgetMb: 3072,
  suggestion: { pageSize: 10000 },
};

describe('runHeavy', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    for (const entry of heavyQueue.getSnapshot()) heavyQueue.remove(entry.id);
  });

  it('consumes a direct response without polling', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(jsonResponse({ value: 7 }));
    const result = await runHeavy(
      () => Promise.resolve(jsonResponse({ value: 7 })),
      response => response.json(),
    );
    expect(result).toEqual({ value: 7 });
    expect(fetch).not.toHaveBeenCalled();
    expect(heavyQueue.getSnapshot()).toHaveLength(0);
  });

  it('asks the user and forces when they choose to run anyway', async () => {
    const starts: boolean[] = [];
    const onOversize = vi.fn(async (): Promise<OversizeChoice> => 'force');
    const result = await runHeavy(
      forced => {
        starts.push(forced);
        return forced
          ? Promise.resolve(jsonResponse({ value: 1 }))
          : Promise.resolve(jsonResponse({ detail: OVERSIZE_DETAIL }, 422));
      },
      response => response.json(),
      { onOversize },
    );
    expect(result).toEqual({ value: 1 });
    expect(starts).toEqual([false, true]);
    expect(onOversize).toHaveBeenCalledWith(expect.objectContaining({ estimatedMb: 4096 }));
  });

  it('applies the suggestion when the user downscales', async () => {
    const applySuggestion = vi.fn();
    const bodies: unknown[] = [];
    const result = await runHeavy(
      () => {
        const first = bodies.length === 0;
        bodies.push(first ? 'refused' : 'downscaled');
        return first
          ? Promise.resolve(jsonResponse({ detail: OVERSIZE_DETAIL }, 422))
          : Promise.resolve(jsonResponse({ value: 2 }));
      },
      response => response.json(),
      { onOversize: async () => 'downscale' },
      applySuggestion,
    );
    expect(result).toEqual({ value: 2 });
    expect(applySuggestion).toHaveBeenCalledWith({ pageSize: 10000 });
    expect(bodies).toEqual(['refused', 'downscaled']);
  });

  it('throws an abort when the user cancels the oversize prompt', async () => {
    await expect(runHeavy(
      () => Promise.resolve(jsonResponse({ detail: OVERSIZE_DETAIL }, 422)),
      response => response.json(),
      { onOversize: async () => 'cancel' },
    )).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('surfaces a structured refusal without a prompt handler', async () => {
    await expect(runHeavy(
      () => Promise.resolve(jsonResponse({ detail: OVERSIZE_DETAIL }, 422)),
      response => response.json(),
    )).rejects.toThrow('estimated to need');
  });

  it('polls an admitted job to completion and updates the queue store', async () => {
    const accepted = jsonResponse({ jobId: 'job-1', kind: 'test', status: 'queued', position: 2 }, 202);
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(jsonResponse({ jobId: 'job-1', status: 'queued', position: 2 }))
      .mockResolvedValueOnce(jsonResponse({ jobId: 'job-1', status: 'running' }))
      .mockResolvedValueOnce(jsonResponse({ jobId: 'job-1', status: 'done', resultKind: 'json' }))
      .mockResolvedValueOnce(jsonResponse({ value: 'done-value' }));

    const result = await runHeavy(
      () => Promise.resolve(accepted),
      response => response.json(),
      { labelKey: 'jobs:labelProcess' },
    );

    expect(result).toEqual({ value: 'done-value' });
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[0][0]).toBe('/api/jobs/job-1');
    expect(calls[calls.length - 1][0]).toBe('/api/jobs/job-1/result');
    expect(heavyQueue.getSnapshot()).toHaveLength(0);
  });

  it('cancels the server job when the caller aborts while queued', async () => {
    const controller = new AbortController();
    const accepted = jsonResponse({ jobId: 'job-2', kind: 'test', status: 'queued', position: 1 }, 202);
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(async (url: string | URL | Request) =>
      String(url).includes('/api/jobs/job-2')
        ? jsonResponse({ jobId: 'job-2', status: 'queued', position: 1 })
        : accepted,
    );

    const promise = runHeavy(
      () => Promise.resolve(accepted),
      response => response.json(),
      { signal: controller.signal },
    );
    // Give the poll loop its first tick, then abort.
    await new Promise(resolve => setTimeout(resolve, 20));
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
    const deleteCalled = (fetch as ReturnType<typeof vi.fn>).mock.calls.some(
      call => call[1]?.method === 'DELETE',
    );
    expect(deleteCalled).toBe(true);
    expect(heavyQueue.getSnapshot()).toHaveLength(0);
  });

  it('throws the job error when the job fails server-side', async () => {
    const accepted = jsonResponse({ jobId: 'job-3', kind: 'test', status: 'queued', position: 1 }, 202);
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(jsonResponse({ jobId: 'job-3', status: 'error', error: 'ValueError: bad input' }));

    await expect(runHeavy(
      () => Promise.resolve(accepted),
      response => response.json(),
    )).rejects.toThrow('bad input');
  });
});
