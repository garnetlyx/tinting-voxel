import { afterEach, describe, expect, it, vi } from 'vitest';
import { submitBugReport } from './client';
import type { BugReportRequest } from './types';

const body = { description: 'Preview problem', frontendContext: {} } as BugReportRequest;
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('Bug report API client', () => {
  it('accepts acknowledged local storage', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, reportId: 'id', delivery: 'stored' }) }));
    await expect(submitBugReport(body)).resolves.toHaveProperty('reportId', 'id');
  });
  it('explains rate limits and rejects unconfirmed success responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429 }));
    await expect(submitBugReport(body)).rejects.toThrow('in an hour');
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
    await expect(submitBugReport(body)).rejects.toThrow('did not confirm');
  });
  it('times out a stalled submission', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    })));
    const result = expect(submitBugReport(body)).rejects.toThrow('timed out');
    await vi.advanceTimersByTimeAsync(25000);
    await result;
  });
});
