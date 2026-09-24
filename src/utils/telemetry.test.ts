import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

async function loadTelemetry() {
  vi.resetModules();
  return import('./telemetry');
}

describe('telemetry client', () => {
  const fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 204 })));

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('batches events and sends them after a short delay', async () => {
    const { track } = await loadTelemetry();
    track('image_selected', { type: 'image/png', sizeMb: 2.5, skipped: undefined });
    track('model_downloaded', { format: 'stl' });
    expect(fetchMock).not.toHaveBeenCalled();

    vi.advanceTimersByTime(5_000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/events');
    expect(init.keepalive).toBe(true);
    const body = JSON.parse(init.body as string);
    expect(body.pageLoadId).toMatch(/^[0-9a-f-]{36}$/);
    expect(body.events.map((event: { name: string }) => event.name)).toEqual(['image_selected', 'model_downloaded']);
    expect(body.events[0].props).toEqual({ type: 'image/png', sizeMb: 2.5 });
  });

  it('sends immediately when a batch fills', async () => {
    const { track } = await loadTelemetry();
    for (let i = 0; i < 20; i += 1) track('client_error', { kind: 'error' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('flushes when the page is hidden', async () => {
    const { initializeTelemetry } = await loadTelemetry();
    initializeTelemetry('en');
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    document.dispatchEvent(new Event('visibilitychange'));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.events[0]).toMatchObject({ name: 'page_view', props: { locale: 'en' } });
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  });

  it('respects Global Privacy Control', async () => {
    Object.defineProperty(navigator, 'globalPrivacyControl', { configurable: true, value: true });
    const { track, flush } = await loadTelemetry();
    track('page_view');
    flush();
    expect(fetchMock).not.toHaveBeenCalled();
    Object.defineProperty(navigator, 'globalPrivacyControl', { configurable: true, value: undefined });
  });
});
