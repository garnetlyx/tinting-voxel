/**
 * Over-budget confirmation for heavy jobs.
 *
 * The API layer catches the server's job_to_large refusal and resolves the
 * user's choice through `oversizeAsk.ask`; this dialog is the single place
 * that choice is made. Framework-free store so plain wrapper functions can
 * open it without React context.
 */
import { useSyncExternalStore } from 'react';
import { i18n } from '../i18n';
import type { OversizeChoice, OversizeInfo, OversizeSuggestion } from '../api/types';

interface PendingAsk {
  info: OversizeInfo;
  resolve: (choice: OversizeChoice) => void;
}

// A queue, not a slot: two heavy calls can be refused together, and each
// promise must resolve even while another dialog is showing.
let pending: PendingAsk[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

export const oversizeAsk = {
  /** Open the dialog; resolves when the user chooses. */
  ask(info: OversizeInfo): Promise<OversizeChoice> {
    return new Promise(resolve => {
      pending = [...pending, { info, resolve }];
      emit();
    });
  },

  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  getSnapshot(): PendingAsk | null {
    return pending[0] ?? null;
  },
};

type LooseT = (key: string, options?: Record<string, unknown>) => string;
const jobsT = (i18n.getFixedT as unknown as (lng: null, ns: string) => LooseT)(null, 'jobs');

function suggestionSummary(suggestion: OversizeSuggestion | undefined): string {
  if (!suggestion) return '';
  const t = jobsT;
  const parts: string[] = [];
  if (suggestion.pageSize !== undefined) {
    parts.push(t('suggestPage', { count: suggestion.pageSize }));
  }
  if (suggestion.layerCount !== undefined) {
    parts.push(t('suggestLayers', { count: suggestion.layerCount }));
  }
  if (suggestion.pixelSize !== undefined) {
    parts.push(t('suggestPitch', { size: suggestion.pixelSize }));
  }
  return parts.join(t('suggestJoin'));
}

export function OversizeDialog() {
  const ask = useSyncExternalStore(oversizeAsk.subscribe, oversizeAsk.getSnapshot);

  if (!ask) return null;
  const { info } = ask;
  const t = jobsT;
  const tCommon = (i18n.getFixedT as unknown as (lng: null, ns: string) => LooseT)(null, 'common');
  const summary = suggestionSummary(info.suggestion);

  const choose = (choice: OversizeChoice): void => {
    ask.resolve(choice);
    pending = pending.slice(1);
    emit();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="oversize-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4"
    >
      <div className="w-full max-w-md rounded-sheet border border-rule bg-paper p-6 shadow-lg">
        <h2 id="oversize-dialog-title" className="mb-3 font-display text-lg text-ink">
          {t('oversizeTitle')}
        </h2>
        <p className="mb-4 text-sm text-ink-muted">
          {t('oversizeBody', {
            estimated: (info.estimatedMb / 1024).toFixed(1),
            budget: (info.budgetMb / 1024).toFixed(1),
          })}
        </p>
        {summary && (
          <p className="mb-4 text-sm text-ink">
            <span className="font-medium">{t('oversizeSuggestionLabel')}</span> {summary}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="tv-btn tv-btn-ghost" onClick={() => choose('cancel')}>
            {tCommon('cancel')}
          </button>
          <button type="button" className="tv-btn tv-btn-ghost" onClick={() => choose('force')}>
            {t('force')}
          </button>
          <button
            type="button"
            className="tv-btn tv-btn-primary"
            onClick={() => choose('downscale')}
            disabled={!info.suggestion}
          >
            {t('downscale')}
          </button>
        </div>
      </div>
    </div>
  );
}
