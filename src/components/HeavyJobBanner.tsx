/**
 * Queue banner for heavy jobs: every entry the API layer is currently
 * following (queued or running server-side) with its cancel control.
 */
import { useSyncExternalStore } from 'react';
import { i18n } from '../i18n';
import { heavyQueue } from '../utils/heavyQueueStore';

type LooseT = (key: string, options?: Record<string, unknown>) => string;

export function HeavyJobBanner() {
  const entries = useSyncExternalStore(heavyQueue.subscribe, heavyQueue.getSnapshot);

  if (entries.length === 0) return null;

  return (
    <div className="mb-6 space-y-2" role="status" aria-live="polite">
      {entries.map(entry => {
        // labelKey is a runtime "namespace:key" pair, outside the typed keys.
        const [namespace, key] = entry.labelKey.split(':');
        const t = (i18n.getFixedT as unknown as (lng: null, ns: string) => LooseT)(null, namespace || 'jobs');
        return (
          <div
            key={entry.id}
            className="flex items-center gap-3 rounded-sheet border border-rule border-l-4 border-l-cyan bg-paper px-4 py-3 text-sm text-ink"
          >
            <span
              aria-hidden="true"
              className="inline-block size-2 shrink-0 animate-pulse rounded-full bg-cyan"
            />
            <span className="min-w-0 flex-1">
              <span className="font-medium">{t(key)}</span>
              {' · '}
              {entry.running ? t('running') : t('queued', { position: entry.position ?? 1 })}
            </span>
            {!entry.running && (
              <button
                type="button"
                className="tv-btn tv-btn-sm"
                onClick={entry.cancel}
              >
                {(i18n.getFixedT as unknown as (lng: null, ns: string) => LooseT)(null, 'common')('cancel')}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
