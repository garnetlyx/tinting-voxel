/**
 * Anonymous first-party usage telemetry (backend: /api/events,
 * services/telemetry.py).
 *
 * Events batch in memory and are sent with fetch keepalive after a short
 * delay, when a batch fills, or when the page is hidden. No cookies or stored
 * identifiers: a random id groups one page load's events, and the server
 * counts visitors with a daily-rotating salted hash. Browsers that send
 * Global Privacy Control or Do Not Track are not tracked. Event and property
 * names follow the server's rules (api/models.py ClientEvent); a batch with an
 * invalid event is rejected whole.
 */
import { sanitizeDiagnostic } from './bugReport';

export type TelemetryValue = string | number | boolean;
export type TelemetryProps = Record<string, TelemetryValue | null | undefined>;

interface QueuedEvent {
  name: string;
  props: Record<string, TelemetryValue>;
  t: number;
}

const ENDPOINT = '/api/events';
const FLUSH_DELAY_MS = 5_000;
const MAX_BATCH = 20;
const MAX_STRING_LENGTH = 200;

const pageLoadId = crypto.randomUUID();
let queue: QueuedEvent[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;
let initialized = false;

function optedOut(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.globalPrivacyControl === true || navigator.doNotTrack === '1';
}

/** Queue one event; null and undefined props are dropped. */
export function track(name: string, props: TelemetryProps = {}): void {
  if (optedOut()) return;
  const clean: Record<string, TelemetryValue> = {};
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined) continue;
    clean[key] = typeof value === 'string' ? value.slice(0, MAX_STRING_LENGTH) : value;
  }
  queue.push({ name, props: clean, t: Math.round(performance.now()) });
  if (queue.length >= MAX_BATCH) flush();
  else timer ??= setTimeout(flush, FLUSH_DELAY_MS);
}

/** Send queued events now. */
export function flush(): void {
  if (timer !== undefined) {
    clearTimeout(timer);
    timer = undefined;
  }
  if (queue.length === 0) return;
  const body = JSON.stringify({ pageLoadId, events: queue });
  queue = [];
  // Telemetry must never disturb the page; a lost batch is acceptable.
  void fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => undefined);
}

/** Record the page view and client errors, and flush when the page is hidden. */
export function initializeTelemetry(locale: string): void {
  if (initialized) return;
  initialized = true;
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
  window.addEventListener('pagehide', flush);
  window.addEventListener('error', event => track('client_error', {
    kind: 'error', detail: sanitizeDiagnostic(event.message || 'Resource failed to load'),
  }));
  window.addEventListener('unhandledrejection', event => track('client_error', {
    kind: 'rejection',
    detail: sanitizeDiagnostic(event.reason instanceof Error ? event.reason.message : String(event.reason)),
  }));
  let referrer = '';
  try {
    referrer = document.referrer ? new URL(document.referrer).hostname : '';
  } catch {
    referrer = '';
  }
  track('page_view', {
    locale,
    referrer,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
  });
}
