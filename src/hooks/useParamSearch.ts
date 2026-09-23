/** State machine for incremental, full-resolution parameter search. */
import { useCallback, useRef, useState } from 'react';
import {
  type ParamSearchConfig,
  type ParamSearchProgress,
  type ParamSearchResponse,
  type SearchResultItem,
  ParamSearchHttpError,
  cancelParamSearch,
  getParamSearchProgress,
  isParamSearchAvailable,
  startParamSearch,
} from '../api/paramSearch';

const POLL_DELAY_MS = 1500;
const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function cancelAndWaitForRelease(jobId: string): Promise<void> {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await cancelParamSearch(jobId);
      break;
    } catch (error) {
      if (error instanceof ParamSearchHttpError && error.status === 404) return;
      if (attempt === 4) throw error;
      await wait(Math.min(POLL_DELAY_MS * 2 ** attempt, 10000));
    }
  }
  while (true) {
    try {
      const progress = await getParamSearchProgress(jobId, 0);
      if (progress.settled) return;
    } catch (error) {
      if (error instanceof ParamSearchHttpError && error.status === 404) return;
      if (error instanceof ParamSearchHttpError && error.status >= 400 && error.status < 500 && error.status !== 429) throw error;
    }
    await wait(POLL_DELAY_MS);
  }
}

export type ParamSearchPhase = 'idle' | 'config' | 'waiting' | 'running' | 'results' | 'error';

interface ParamSearchState {
  phase: ParamSearchPhase;
  progress: ParamSearchProgress | null;
  results: SearchResultItem[];
  error: string | null;
}

interface UseParamSearchReturn extends ParamSearchState {
  openConfig: () => void;
  startSearch: (
    imageFile: File,
    config: ParamSearchConfig,
    imageDimensions: { width: number; height: number },
  ) => Promise<void>;
  reset: () => void;
}

const emptyState = (phase: ParamSearchPhase): ParamSearchState => ({
  phase, progress: null, results: [], error: null,
});

export function useParamSearch(): UseParamSearchReturn {
  const [state, setState] = useState<ParamSearchState>(emptyState('idle'));
  const activeJobRef = useRef<string | null>(null);
  const pendingStartRef = useRef<Promise<ParamSearchResponse> | null>(null);
  const releaseRef = useRef<Promise<void> | null>(null);
  const generationRef = useRef(0);

  const releaseCurrentJob = useCallback((): Promise<void> | null => {
    if (releaseRef.current) return releaseRef.current;
    const jobId = activeJobRef.current;
    const pending = pendingStartRef.current;
    activeJobRef.current = null;
    if (!jobId && !pending) return null;
    const release = jobId
      ? cancelAndWaitForRelease(jobId)
      : pending!.then((response) => cancelAndWaitForRelease(response.jobId), () => undefined);
    releaseRef.current = release;
    void release.then(
      () => { if (releaseRef.current === release) releaseRef.current = null; },
      () => { if (releaseRef.current === release) releaseRef.current = null; },
    );
    return release;
  }, []);

  const openConfig = useCallback(() => {
    setState(emptyState(releaseRef.current ? 'waiting' : 'config'));
  }, []);

  const startSearch = useCallback(
    async (
      imageFile: File,
      config: ParamSearchConfig,
      imageDimensions: { width: number; height: number },
    ) => {
      const generation = ++generationRef.current;
      try {
        const release = releaseCurrentJob();
        if (release) {
          setState(emptyState('waiting'));
          await release;
        }
        if (generation !== generationRef.current) return;
        setState(emptyState('running'));

        while (generation === generationRef.current) {
          let response: ParamSearchResponse;
          const pending = startParamSearch(imageFile, config, imageDimensions);
          pendingStartRef.current = pending;
          try {
            response = await pending;
          } catch (error) {
            if (generation !== generationRef.current) return;
            if (error instanceof ParamSearchHttpError && error.status === 429 && error.retryAfterMs) {
              setState(emptyState('waiting'));
              await wait(error.retryAfterMs + 100);
              continue;
            }
            if (error instanceof ParamSearchHttpError && error.status === 503) {
              setState(emptyState('waiting'));
              while (generation === generationRef.current) {
                try {
                  if (await isParamSearchAvailable()) break;
                } catch (availabilityError) {
                  if (availabilityError instanceof ParamSearchHttpError && availabilityError.status >= 400 && availabilityError.status < 500 && availabilityError.status !== 429) throw availabilityError;
                }
                await wait(POLL_DELAY_MS);
              }
              continue;
            }
            throw error;
          } finally {
            if (pendingStartRef.current === pending) pendingStartRef.current = null;
          }
          if (generation !== generationRef.current) return;
          activeJobRef.current = response.jobId;
          setState(emptyState('running'));
          let after = 0;

          while (generation === generationRef.current) {
            let progress: ParamSearchProgress;
            try {
              progress = await getParamSearchProgress(response.jobId, after);
            } catch (error) {
              if (error instanceof ParamSearchHttpError && error.status >= 400 && error.status < 500 && error.status !== 429) throw error;
              await wait(POLL_DELAY_MS);
              continue;
            }
            if (generation !== generationRef.current) return;
            for (const result of progress.results) after = Math.max(after, result.candidateId);
            setState((previous) => {
              const results = [...previous.results, ...progress.results];
              const complete = progress.status === 'complete';
              const failed = progress.status === 'error' || progress.status === 'cancelled' || (complete && results.length === 0);
              return {
                phase: failed ? 'error' : complete ? 'results' : 'running',
                progress, results,
                error: failed ? progress.error ?? 'Search ended before a preview was ready' : null,
              };
            });
            if (progress.status !== 'running' && progress.settled) {
              activeJobRef.current = null;
              return;
            }
            await wait(POLL_DELAY_MS);
          }
        }
      } catch (error) {
        if (generation !== generationRef.current) return;
        setState((previous) => ({
          ...previous,
          phase: 'error',
          error: error instanceof Error ? error.message : String(error),
        }));
      }
    },
    [releaseCurrentJob],
  );

  const reset = useCallback(() => {
    const generation = ++generationRef.current;
    const release = releaseCurrentJob();
    setState(emptyState(release ? 'waiting' : 'idle'));
    if (release) {
      void release.then(
        () => { if (generation === generationRef.current) setState(emptyState('idle')); },
        (error) => {
          if (generation === generationRef.current) {
            setState({ ...emptyState('error'), error: error instanceof Error ? error.message : String(error) });
          }
        },
      );
    }
  }, [releaseCurrentJob]);

  return { ...state, openConfig, startSearch, reset };
}
