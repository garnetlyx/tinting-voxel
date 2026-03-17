/**
 * State machine hook for parameter search.
 * Phases: idle → config → running → results | error
 */
import { useCallback, useRef, useState } from 'react';
import {
  type ParamSearchConfig,
  type ParamSearchProgress,
  type SearchResultItem,
  startParamSearch,
  subscribeToProgress,
} from '../api/paramSearch';

export type ParamSearchPhase = 'idle' | 'config' | 'running' | 'results' | 'error';

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

export function useParamSearch(): UseParamSearchReturn {
  const [state, setState] = useState<ParamSearchState>({
    phase: 'idle',
    progress: null,
    results: [],
    error: null,
  });

  const cleanupRef = useRef<(() => void) | null>(null);

  const openConfig = useCallback(() => {
    setState({ phase: 'config', progress: null, results: [], error: null });
  }, []);

  const startSearch = useCallback(
    async (
      imageFile: File,
      config: ParamSearchConfig,
      imageDimensions: { width: number; height: number },
    ) => {
      setState({ phase: 'running', progress: null, results: [], error: null });

      try {
        const response = await startParamSearch(imageFile, config, imageDimensions);

        // Open SSE stream for progress updates
        const cleanup = subscribeToProgress(
          response.jobId,
          (event) => {
            setState((prev) => ({ ...prev, progress: event }));
          },
          () => {
            setState((prev) => ({
              ...prev,
              phase: 'results',
              results: response.results,
            }));
          },
          (err) => {
            setState((prev) => ({
              ...prev,
              phase: 'error',
              error: err.message,
            }));
          },
        );
        cleanupRef.current = cleanup;

        // If the search already completed synchronously (no SSE events expected),
        // transition to results immediately.
        if (response.results.length > 0) {
          setState((prev) => {
            if (prev.phase === 'running') {
              return { ...prev, phase: 'results', results: response.results };
            }
            return prev;
          });
        }
      } catch (err) {
        setState({
          phase: 'error',
          progress: null,
          results: [],
          error: err instanceof Error ? err.message : String(err),
        });
      }
    },
    [],
  );

  const reset = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState({ phase: 'idle', progress: null, results: [], error: null });
  }, []);

  return {
    ...state,
    openConfig,
    startSearch,
    reset,
  };
}
