import React, { useEffect, useState } from 'react';
import { useLocalizedMessage } from '../i18n/messages';
import { useParameterLabel } from '../i18n/catalog';
import { useTranslation } from '../i18n';
import { isValidSearchTargetEdgeMm, maxSearchTargetEdgeMm, type ImageDimensions, type ParamSearchProgress, type SearchResultItem } from '../api/paramSearch';
import type { ParamSearchPhase } from '../hooks/useParamSearch';
import { X } from 'lucide-react';

interface ParamSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  phase: ParamSearchPhase;
  progress: ParamSearchProgress | null;
  results: SearchResultItem[];
  error: string | null;
  onStart: (targetLongestEdgeMm: number) => void;
  onApplyParams: (params: Record<string, number>, mode: string, targetLongestEdgeMm: number) => void;
  imageDimensions: ImageDimensions;
  defaultTargetSizeMm?: number;
}

export const ParamSearchModal: React.FC<ParamSearchModalProps> = ({
  isOpen, onClose, phase, progress, results, error, onStart, onApplyParams, imageDimensions, defaultTargetSizeMm,
}) => {
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
  const parameterLabel = useParameterLabel();
  const [targetSize, setTargetSize] = useState(String(defaultTargetSizeMm ?? 100));
  const targetMm = targetSize.trim() === '' ? NaN : Number(targetSize);
  const maxTargetMm = maxSearchTargetEdgeMm(imageDimensions);
  const targetValid = isValidSearchTargetEdgeMm(targetMm, imageDimensions);

  useEffect(() => {
    if (isOpen && defaultTargetSizeMm && defaultTargetSizeMm > 0) {
      setTargetSize(String(defaultTargetSizeMm));
    }
  }, [isOpen, defaultTargetSizeMm]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Closest match first; ties keep evaluation order. The ranking is live while
  // the search runs, and selecting any card applies it and stops the search.
  const ranked = [...results].sort((a, b) => a.score - b.score || a.candidateId - b.candidateId);
  const currentScore = results.find((result) => result.isBaseline)?.score;
  const searchFinished = phase === 'results';

  const cards = (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {ranked.map((result, index) => {
        const label = result.isBaseline ? t('search:currentSettings') : t('search:candidate', { number: result.candidateId });
        const best = index === 0;
        const delta = currentScore === undefined || result.isBaseline ? null : result.score - currentScore;
        return (
          <button key={result.candidateId} onClick={() => {
            onApplyParams(result.params, result.mode, targetMm);
            onClose();
          }} className={`rounded-sheet border bg-paper-raised p-3 text-left transition-all hover:border-ink hover:shadow-lift ${best ? 'border-magenta-deep shadow-lift' : 'border-rule'}`}>
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-xs text-ink-muted" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
              <span className="text-sm font-semibold text-ink">{label}</span>
              <span className="font-mono text-xs text-ink-muted">{t(result.mode === 'pixel' ? 'search:modePixel' : 'search:modeSvg')}</span>
              {best && (
                <span className={`ml-auto rounded-[2px] px-1.5 py-0.5 text-[0.6875rem] font-semibold uppercase tracking-wide ${searchFinished ? 'bg-magenta-deep text-paper-raised' : 'border border-magenta-deep text-magenta-deep'}`}>
                  {t(searchFinished ? 'search:bestMatch' : 'search:bestSoFar')}
                </span>
              )}
            </div>
            <img src={result.previewImage} alt={label} className="mb-2 w-full rounded-[2px] border border-rule object-contain" style={{ maxHeight: 180 }} />
            <div className="mb-2 border-b border-rule pb-2">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xs text-ink-muted">{t('search:colorDifference')}</span>
                <span className="font-mono text-base font-medium text-ink">ΔE {result.score.toFixed(2)}</span>
              </div>
              {delta !== null && (
                <p className={`mt-0.5 text-right text-xs ${delta < 0 ? 'text-signal-ok' : 'text-ink-muted'}`}>
                  {t(delta < 0 ? 'search:closerThanCurrent' : 'search:furtherThanCurrent', { value: Math.abs(delta).toFixed(2) })}
                </p>
              )}
            </div>
            <div className="space-y-0.5 text-xs text-ink-muted">
              {Object.entries(result.params).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <span>{parameterLabel(key)}</span><span className="font-mono text-ink">{Number.isInteger(value) ? value : value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );

  const ranking = (
    <>
      <div className="space-y-1">
        <p className="text-sm text-ink-soft">{phase === 'running' ? t('search:runningNote') : t('search:results', { count: results.length })}</p>
        <p className="tv-help">{t('search:scoreNote')}</p>
      </div>
      {cards}
    </>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-[2px]" role="dialog" aria-modal="true" aria-label={t('search:autoOptimizeParameters')}>
      <div className="tv-sheet max-h-[90dvh] w-full max-w-2xl overflow-y-auto">
        <div className="flex items-center justify-between border-b border-rule px-6 py-4">
          <h2 className="tv-heading text-xl">{t('search:autoOptimizeParameters')}</h2>
          <button onClick={onClose} className="rounded-sheet p-1.5 text-ink-muted hover:bg-paper-sunk hover:text-ink" aria-label={t('common:close')}>
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="p-6">
          {phase === 'config' && (
            <div className="space-y-5">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-ink-soft" htmlFor="targetSize">{t('search:targetLongestEdgeMm')}</label>
                <input id="targetSize" type="number" min="0" max={maxTargetMm} step="any" value={targetSize}
                  aria-invalid={!targetValid}
                  onChange={(event) => setTargetSize(event.target.value)}
                  className="tv-input font-mono" />
                {!targetValid && <p role="alert" className="mt-1 text-sm text-signal-error">{t('search:invalidTargetEdge', { max: maxTargetMm })}</p>}
              </div>
              <button disabled={!targetValid} onClick={() => onStart(targetMm)} className="tv-btn-primary w-full !py-2.5">
                {t('search:startOptimization')}
              </button>
            </div>
          )}
          {phase === 'waiting' && (
            <div className="space-y-4">
              <p className="text-sm text-ink-soft">{t('search:waitingToStart')}</p>
              <button onClick={onClose} className="tv-btn-outline w-full">{t('common:close')}</button>
            </div>
          )}
          {phase === 'running' && (
            <div className="space-y-4">
              <p className="text-sm text-ink-soft">{t('search:searchingForOptimalParametersPleaseWait')}</p>
              {progress && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-ink-soft">
                    <span>{t('search:progress')}</span><span className="font-mono">{progress.completed} / {progress.total}</span>
                  </div>
                  <progress value={progress.completed} max={progress.total || 1} className="h-1.5 w-full overflow-hidden rounded-full accent-ink" />
                </div>
              )}
              {results.length > 0 && ranking}
              <button onClick={onClose} className="tv-btn-outline w-full">{t('common:close')}</button>
            </div>
          )}
          {phase === 'results' && (
            <div className="space-y-4">
              {ranking}
              <button onClick={onClose} className="tv-btn-outline w-full">{t('common:close')}</button>
            </div>
          )}
          {phase === 'error' && (
            <div className="space-y-4">
              <div className="rounded-sheet border border-signal-error/30 border-l-4 border-l-signal-error bg-signal-error/5 p-4"><p className="text-sm text-signal-error">{localize(error ?? 'Failed to start parameter search')}</p></div>
              {results.length > 0 && ranking}
              <div className="flex gap-3">
                <button disabled={!targetValid} onClick={() => onStart(targetMm)} className="tv-btn-primary flex-1">{t('common:retry')}</button>
                <button onClick={onClose} className="tv-btn-outline flex-1">{t('common:close')}</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ParamSearchModal;
