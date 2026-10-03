/**
 * Queue-aware submission for memory-heavy endpoints.
 *
 * The server keeps at most one heavy job running; a request that arrives
 * while it is busy is admitted as a job and answered with 202 {jobId,
 * position}. This wrapper polls that job to completion, keeps the queue
 * banner updated, cancels the server-side job when the caller aborts, and
 * turns an over-budget refusal (422 job_too_large) into a user choice:
 * apply the server's scale-down suggestion, run anyway (forceOversize), or
 * cancel.
 */
import { heavyQueue } from '../utils/heavyQueueStore';
import { track } from '../utils/telemetry';
import type { HeavyCallOptions, OversizeInfo, OversizeSuggestion } from './types';
import { getErrorDetail } from './errors';

const POLL_INTERVAL_MS = 800;

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly estimatedMb?: number;
  readonly budgetMb?: number;
  readonly suggestion?: OversizeSuggestion;

  constructor(message: string, status: number, extra: Partial<OversizeInfo & { code: string }> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = extra.code;
    this.estimatedMb = extra.estimatedMb;
    this.budgetMb = extra.budgetMb;
    this.suggestion = extra.suggestion;
  }
}

interface JobAccepted {
  jobId: string;
  kind: string;
  status: string;
  position: number;
}

function abortError(): DOMException {
  return new DOMException('Heavy call aborted', 'AbortError');
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(abortError());
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort(): void {
      window.clearTimeout(timer);
      reject(abortError());
    }
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/** Fire-and-forget cancellation of a server-side queued job. */
function cancelServerJob(jobId: string): void {
  void fetch(`/api/jobs/${jobId}`, { method: 'DELETE' }).catch(() => {
    // The job may already be gone; nothing to recover.
  });
}

/**
 * Submit one heavy call, following it through queue and result fetch.
 *
 * @param start performs the endpoint POST; `forced` marks the user's
 *   "run it anyway" confirmation (forceOversize).
 * @param consume turns the final response (direct or job result) into the
 *   caller's value — e.g. JSON parse or a file download.
 * @param applySuggestion mutates the request parameters per the server's
 *   scale-down suggestion before the downscale retry.
 */
export async function runHeavy<T>(
  start: (forced: boolean) => Promise<Response>,
  consume: (response: Response) => Promise<T>,
  opts: HeavyCallOptions = {},
  applySuggestion?: (suggestion: OversizeSuggestion) => void,
  fallbackMessage = 'Request failed',
): Promise<T> {
  let response = await start(false);

  if (response.status === 422) {
    const error = await toOversizeError(response);
    if (error?.code === 'job_too_large' && opts.onOversize) {
      track('oversize_prompt', { estimated_mb: Math.round(error.estimatedMb ?? 0) });
      const choice = await opts.onOversize({
        estimatedMb: error.estimatedMb ?? 0,
        budgetMb: error.budgetMb ?? 0,
        suggestion: error.suggestion,
      });
      track('oversize_choice', { choice });
      if (choice === 'cancel') throw abortError();
      if (choice === 'downscale' && error.suggestion) {
        applySuggestion?.(error.suggestion);
        opts.onSuggestionApplied?.(error.suggestion);
      }
      response = await start(choice === 'force');
    } else if (error) {
      throw error;
    } else {
      throw new Error(await getErrorDetail(response, fallbackMessage));
    }
  }

  if (response.status === 202) {
    const accepted = (await response.json()) as JobAccepted;
    return pollJob(accepted, consume, opts);
  }
  if (!response.ok) {
    throw new Error(await getErrorDetail(response, fallbackMessage));
  }
  return consume(response);
}

async function toOversizeError(response: Response): Promise<ApiError | null> {
  try {
    const body = await response.clone().json();
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && detail.code) {
      return new ApiError(String(detail.message ?? 'Job too large'), response.status, detail);
    }
  } catch {
    // Not a structured error body.
  }
  return null;
}

async function pollJob<T>(
  accepted: JobAccepted,
  consume: (response: Response) => Promise<T>,
  opts: HeavyCallOptions,
): Promise<T> {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort();
  opts.signal?.addEventListener('abort', forwardAbort, { once: true });
  if (opts.signal?.aborted) controller.abort();

  const entryId = heavyQueue.add({
    id: accepted.jobId,
    labelKey: opts.labelKey ?? 'jobs:labelJob',
    position: accepted.position,
    running: false,
    cancel: () => controller.abort(),
  });
  track('job_queued', { position: accepted.position });

  try {
    for (;;) {
      await sleep(POLL_INTERVAL_MS, controller.signal);
      const statusResponse = await fetch(`/api/jobs/${accepted.jobId}`, {
        signal: controller.signal,
      });
      if (!statusResponse.ok) {
        throw new Error(await getErrorDetail(statusResponse, 'Lost track of the queued job'));
      }
      const snapshot = await statusResponse.json();
      if (snapshot.status === 'queued') {
        heavyQueue.update(entryId, { position: snapshot.position, running: false });
      } else if (snapshot.status === 'running') {
        heavyQueue.update(entryId, { running: true });
      } else if (snapshot.status === 'done') {
        const result = await fetch(`/api/jobs/${accepted.jobId}/result`, {
          signal: controller.signal,
        });
        if (!result.ok) {
          throw new Error(await getErrorDetail(result, 'Failed to fetch the job result'));
        }
        return consume(result);
      } else if (snapshot.status === 'cancelled') {
        track('job_cancelled', {});
        throw abortError();
      } else {
        throw new Error(String(snapshot.error ?? 'Job failed'));
      }
    }
  } catch (error) {
    if (controller.signal.aborted) {
      track('job_cancelled', {});
      cancelServerJob(accepted.jobId);
      throw abortError();
    }
    throw error;
  } finally {
    opts.signal?.removeEventListener('abort', forwardAbort);
    heavyQueue.remove(entryId);
  }
}
