import React, { useEffect, useState } from 'react';
import { useLocalizedMessage } from '../i18n/messages';
import { useParameterLabel } from '../i18n/catalog';
import { useTranslation } from '../i18n';
import { isValidSearchTargetEdgeMm, maxSearchTargetEdgeMm, type ImageDimensions, type ParamSearchProgress, type SearchResultItem } from '../api/paramSearch';
import type { ParamSearchPhase } from '../hooks/useParamSearch';

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

  const cards = (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {results.map((result) => {
        const label = result.isBaseline ? t('search:currentSettings') : t('search:candidate', { number: result.candidateId });
        return (
          <button key={result.candidateId} onClick={() => {
            onApplyParams(result.params, result.mode, targetMm);
            onClose();
          }} className="text-left rounded-xl border border-gray-200 p-3 hover:border-purple-400 hover:shadow-md">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-purple-700">{label}</span>
              <span className="text-xs text-gray-500">{t(result.mode === 'pixel' ? 'search:modePixel' : 'search:modeSvg')}</span>
            </div>
            <img src={result.previewImage} alt={label} className="w-full rounded-lg mb-2 object-contain" style={{ maxHeight: 180 }} />
            <div className="text-xs text-gray-500 space-y-0.5">
              {Object.entries(result.params).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span>{parameterLabel(key)}</span><span className="font-mono">{Number.isInteger(value) ? value : value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-label={t('search:autoOptimizeParameters')}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-800">{t('search:autoOptimizeParameters')}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label={t('common:close')}>✕</button>
        </div>
        <div className="p-6">
          {phase === 'config' && (
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="targetSize">{t('search:targetLongestEdgeMm')}</label>
                <input id="targetSize" type="number" min="0" max={maxTargetMm} step="any" value={targetSize}
                  aria-invalid={!targetValid}
                  onChange={(event) => setTargetSize(event.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
                {!targetValid && <p role="alert" className="mt-1 text-sm text-red-700">{t('search:invalidTargetEdge', { max: maxTargetMm })}</p>}
              </div>
              <button disabled={!targetValid} onClick={() => onStart(targetMm)} className="w-full py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium disabled:opacity-50">
                {t('search:startOptimization')}
              </button>
            </div>
          )}
          {phase === 'waiting' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">{t('search:waitingToStart')}</p>
              <button onClick={onClose} className="w-full py-2 border border-gray-300 rounded-lg">{t('common:close')}</button>
            </div>
          )}
          {phase === 'running' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">{t('search:searchingForOptimalParametersPleaseWait')}</p>
              {progress && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>{t('search:progress')}</span><span>{progress.completed} / {progress.total}</span>
                  </div>
                  <progress value={progress.completed} max={progress.total || 1} className="w-full" />
                </div>
              )}
              {results.length > 0 && (
                <>
                  <p className="text-sm text-gray-600">{t('search:results', { count: results.length })}</p>
                  {cards}
                </>
              )}
              <button onClick={onClose} className="w-full py-2 border border-gray-300 rounded-lg">{t('common:close')}</button>
            </div>
          )}
          {phase === 'results' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">{t('search:results', { count: results.length })}</p>
              {cards}
              <button onClick={onClose} className="w-full py-2 border border-gray-300 rounded-lg">{t('common:close')}</button>
            </div>
          )}
          {phase === 'error' && (
            <div className="space-y-4">
              <div className="rounded-lg bg-red-50 border border-red-200 p-4"><p className="text-sm text-red-700">{localize(error ?? 'Failed to start parameter search')}</p></div>
              {results.length > 0 && (
                <>
                  <p className="text-sm text-gray-600">{t('search:results', { count: results.length })}</p>
                  {cards}
                </>
              )}
              <div className="flex gap-3">
                <button disabled={!targetValid} onClick={() => onStart(targetMm)} className="flex-1 py-2 bg-purple-600 text-white rounded-lg disabled:opacity-50">{t('common:retry')}</button>
                <button onClick={onClose} className="flex-1 py-2 border border-gray-300 rounded-lg">{t('common:close')}</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ParamSearchModal;
