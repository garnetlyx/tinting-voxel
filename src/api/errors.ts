/**
 * Shared API error extraction: FastAPI validation details, rate limits and
 * edge failures, as user-readable messages.
 */
import { recordBugReportLog } from '../utils/bugReport';
import { track } from '../utils/telemetry';
import type { OversizeSuggestion } from './types';

/** Milliseconds to wait from a Retry-After header (seconds or HTTP date). */
export function retryAfterMs(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  const delay = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(value) - Date.now();
  return Number.isFinite(delay) && delay > 0 ? delay : undefined;
}

/** Canonical rate-limit message; the i18n adapter localizes it. */
function rateLimitMessage(retryAfter: string | null): string {
  const delay = retryAfterMs(retryAfter);
  return delay === undefined
    ? 'Too many requests. Please try again shortly.'
    : `Too many requests. Please try again in ${Math.ceil(delay / 1000)} seconds.`;
}

/** Request path with generated IDs masked, so failures group by endpoint. */
export function apiPath(url: string): string {
  try {
    return new URL(url).pathname.replace(/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/gi, '{id}');
  } catch {
    return '';
  }
}

/** Turn a structured oversize refusal body into its parts, if it is one. */
export function parseOversizeDetail(detail: unknown): {
  code: string;
  message: string;
  estimatedMb?: number;
  budgetMb?: number;
  suggestion?: OversizeSuggestion;
} | null {
  if (!detail || typeof detail !== 'object') return null;
  const candidate = detail as Record<string, unknown>;
  if (typeof candidate.code !== 'string') return null;
  return {
    code: candidate.code,
    message: String(candidate.message ?? 'Request failed'),
    estimatedMb: typeof candidate.estimatedMb === 'number' ? candidate.estimatedMb : undefined,
    budgetMb: typeof candidate.budgetMb === 'number' ? candidate.budgetMb : undefined,
    suggestion: (candidate.suggestion ?? undefined) as OversizeSuggestion | undefined,
  };
}

/**
 * Safely extract error detail from a response that may not be JSON
 * FastAPI validation errors return detail as an array of objects
 */
export async function getErrorDetail(response: Response, fallback: string): Promise<string> {
  recordBugReportLog('error', `API request failed (${response.status}): ${response.url || fallback}`);
  // Edge failures (for example a proxy timeout) never reach the backend's logs.
  track('api_failed', { status: response.status, path: apiPath(response.url) });
  if (response.status === 429) return rateLimitMessage(response.headers?.get('Retry-After') ?? null);
  try {
    const body = await response.json();
    const detail = body.detail;

    // Structured refusal (job_too_large): its message is user-ready.
    const structured = parseOversizeDetail(detail);
    if (structured) return structured.message;

    // FastAPI validation errors return detail as an array: [{type, loc, msg, ...}]
    if (Array.isArray(detail)) {
      // Extract the first error message, or join all messages
      const messages = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).filter(Boolean);
      return messages.length > 0 ? messages.join('; ') : fallback;
    }

    // String detail
    if (typeof detail === 'string') {
      return detail;
    }

    return fallback;
  } catch {
    return fallback;
  }
}
