import { useLocalizedMessage } from '../i18n/messages';
import { usePresetLabel, useParameterLabel } from '../i18n/catalog';
import { useTranslation } from '../i18n';
/**
 * Parameter search modal component.
 * Manages four phases: config → running → results | error
 */
import React, { useEffect, useState } from 'react';
import type { SearchResultItem } from '../api/paramSearch';
import type { ParamSearchPhase } from '../hooks/useParamSearch';
import type { ParamSearchProgress } from '../api/paramSearch';

import { FILAMENT_PRESET_OPTIONS, DEFAULT_FILAMENT_PRESET } from '../api/types';

interface ParamSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  phase: ParamSearchPhase;
  progress: ParamSearchProgress | null;
  results: SearchResultItem[];
  error: string | null;
  onStart: (targetLongestEdgeMm: number, preset: string) => void;
  onApplyParams: (params: Record<string, number>, mode: string) => void;
}

export const ParamSearchModal: React.FC<ParamSearchModalProps> = ({
  isOpen,
  onClose,
  phase,
  progress,
  results,
  error,
  onStart,
  onApplyParams,
}) => {
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
  const presetLabel = usePresetLabel();
  const parameterLabel = useParameterLabel();
  const [targetSize, setTargetSize] = useState(100);
  const [preset, setPreset] = useState<string>(DEFAULT_FILAMENT_PRESET);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const top5 = results.slice(0, 5);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-label={t('search:autoOptimizeParameters')}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-800">{t('search:autoOptimizeParameters')}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label={t('common:close')}
          >
            ✕
          </button>
        </div>

        <div className="p-6">
          {/* Phase 1: Config */}
          {phase === 'config' && (
            <div className="space-y-5">
              <p className="text-sm text-gray-600">{t('search:optimizerHelp')}</p>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="targetSize">{t('search:targetLongestEdgeMm')}</label>
                <input
                  id="targetSize"
                  type="number"
                  min={10}
                  max={500}
                  step={10}
                  value={targetSize}
                  onChange={(e) => setTargetSize(Number(e.target.value))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">{t('search:targetSizeHelp')}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="presetSelect">{t('search:filamentPreset')}</label>
                <select
                  id="presetSelect"
                  value={preset}
                  onChange={(e) => setPreset(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  {FILAMENT_PRESET_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{presetLabel(o.value, o.label)}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => onStart(targetSize, preset)}
                className="w-full py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium"
              >{t('search:startOptimization')}</button>
            </div>
          )}

          {/* Phase 2: Running */}
          {phase === 'running' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">{t('search:searchingForOptimalParametersPleaseWait')}</p>
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-gray-600">
                  <span>{t('search:progress')}</span>
                  <span>
                    {progress ? `${progress.completed} / ${progress.total}` : '—'}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className="bg-purple-600 h-3 rounded-full transition-all duration-300"
                    style={{
                      width: progress && progress.total > 0
                        ? `${Math.round((progress.completed / progress.total) * 100)}%`
                        : '0%',
                    }}
                  />
                </div>
                {progress && (
                  <p className="text-xs text-gray-500">{t('search:currentBestMae')}{' '}{progress.bestMae.toFixed(2)}
                  </p>
                )}
              </div>
              <button
                onClick={onClose}
                className="w-full py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >{t('common:cancel')}</button>
            </div>
          )}

          {/* Phase 3: Results */}
          {phase === 'results' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                {t('search:results', { count: results.length })}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {top5.map((r) => (
                  <button
                    key={`${r.rank}-${r.mode === 'pixel' ? t('search:modePixel') : r.mode === 'svg' ? t('search:modeSvg') : r.mode}`}
                    onClick={() => {
                      onApplyParams(r.params, r.mode);
                      onClose();
                    }}
                    className={`text-left rounded-xl border p-3 hover:border-purple-400 hover:shadow-md transition-all ${
                      r.rank === 1 ? 'border-purple-500 ring-2 ring-purple-200' : 'border-gray-200'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-semibold text-purple-700">#{r.rank}</span>
                      <span className="text-xs text-gray-500 uppercase">{r.mode}</span>
                      {r.rank === 1 && (
                        <span className="ml-auto text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{t('search:best')}</span>
                      )}
                    </div>
                    <img
                      src={r.previewImage}
                      alt={t('search:rankPreview', { rank: r.rank })}
                      className="w-full rounded-lg mb-2 object-cover"
                      style={{ maxHeight: 120 }}
                    />
                    <p className="text-xs text-gray-600 mb-1">{t('search:mae')}{' '}{r.mae.toFixed(2)}</p>
                    <div className="text-xs text-gray-500 space-y-0.5">
                      {Object.entries(r.params).map(([k, v]) => (
                        <div key={k} className="flex justify-between">
                          <span>{parameterLabel(k)}</span>
                          <span className="font-mono">{typeof v === 'number' ? v.toFixed(2) : v}</span>
                        </div>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
              <button
                onClick={onClose}
                className="w-full py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >{t('common:close')}</button>
            </div>
          )}

          {/* Phase 4: Error */}
          {phase === 'error' && (
            <div className="space-y-4">
              <div className="rounded-lg bg-red-50 border border-red-200 p-4">
                <p className="text-sm text-red-700">{localize(error ?? 'Optimization failed. Please try again.')}</p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => onStart(targetSize, preset)}
                  className="flex-1 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                >{t('common:retry')}</button>
                <button
                  onClick={onClose}
                  className="flex-1 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >{t('common:close')}</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ParamSearchModal;
