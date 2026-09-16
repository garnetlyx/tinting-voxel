import { useTranslation } from '../i18n';
/**
 * Panel for configuring filament colors with preset quick-load and custom editing
 */
import React from 'react';
import { Plus } from 'lucide-react';
import type { FilamentPreset, FilamentColorConfig } from '../api/types';
import { PresetSelector } from './PresetSelector';
import { FilamentColorRow } from './FilamentColorRow';

const MAX_FILAMENT_COLORS = 16;
const MIN_FILAMENT_COLORS = 4;

interface FilamentConfigPanelProps {
  filamentPreset: FilamentPreset | null;
  filamentColors: FilamentColorConfig[];
  isValid: boolean;
  onLoadPreset: (preset: FilamentPreset) => void;
  onUpdateColor: (index: number, updated: FilamentColorConfig) => void;
  onAddColor: () => void;
  onRemoveColor: (index: number) => void;
  disabled?: boolean;
}

export const FilamentConfigPanel: React.FC<FilamentConfigPanelProps> = ({
  filamentPreset,
  filamentColors,
  isValid,
  onLoadPreset,
  onUpdateColor,
  onAddColor,
  onRemoveColor,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const existingLabels = filamentColors.map(c => c.name?.[0]?.toUpperCase() ?? '');
  const canAdd = filamentColors.length < MAX_FILAMENT_COLORS;
  const canRemove = filamentColors.length > MIN_FILAMENT_COLORS;

  return (
    <div className="space-y-3">
      {/* Preset quick-load */}
      <PresetSelector
        selectedPreset={filamentPreset}
        onPresetChange={onLoadPreset}
        disabled={disabled}
      />

      {/* Color rows */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 font-medium">
            {t('filaments:capacity', { count: filamentColors.length, max: MAX_FILAMENT_COLORS })}
          </span>
          {!isValid && (
            <span className="text-xs text-red-500 font-medium">{t('filaments:fixValidationErrorsBelow')}</span>
          )}
        </div>

        <p className="text-xs text-gray-500">{t('filaments:codeHelp')}</p>
        {/* Column headers */}
        <div className="flex items-center gap-2 text-xs text-gray-400 px-0.5">
          <span className="w-8">{t('filaments:hex')}</span>
          <span className="flex-1">{t('filaments:codeName')}</span>
          <span className="w-20 text-right">{t('filaments:td')}</span>
          <span className="w-6"></span>
        </div>

        {filamentColors.map((config, index) => (
          <FilamentColorRow
            key={index}
            config={config}
            index={index}
            onChange={onUpdateColor}
            onRemove={onRemoveColor}
            canRemove={canRemove}
            existingLabels={existingLabels}
          />
        ))}
      </div>

      {/* Add color button */}
      <button
        onClick={onAddColor}
        disabled={!canAdd || disabled}
        className="flex items-center gap-1 text-sm text-purple-600 hover:text-purple-800 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        <Plus className="w-4 h-4" />{t('filaments:addColor')}</button>

      {/* Scalar-form compensation (paper Eqs. 1-2) is a set-level fit:
          one shared alpha_s/s_td/gamma_td applied to every scalar-TD color.
          Editing here writes the value to all scalar rows at once. */}
      {filamentColors.some((c) => !c.td_rgb) && (
        <div className="pt-1 border-t border-gray-100">
          <div className="text-xs text-gray-500 font-medium mt-2">{t('filaments:compensationGroup')}</div>
          <p className="text-xs text-gray-400 mb-1">{t('filaments:compensationAppliesTo')}</p>
          <div className="flex items-center gap-2">
            {([
              ['alpha_s', 'alphaSLabel', 2.302585092994046],
              ['td_scale', 'tdScaleLabel', 1],
              ['td_gamma', 'tdGammaLabel', 1],
            ] as const).map(([field, labelKey, neutral]) => {
              const scalarRows = filamentColors
                .map((c, i) => ({ c, i }))
                .filter(({ c }) => !c.td_rgb);
              const current = (scalarRows[0]?.c[field] as number | undefined) ?? neutral;
              return (
                <input
                  key={field}
                  type="number"
                  aria-label={t(`filaments:${labelKey}`)}
                  value={current}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    if (isNaN(val) || val <= 0 || val > 1000) return;
                    scalarRows.forEach(({ c, i }) =>
                      onUpdateColor(i, { ...c, [field]: val })
                    );
                  }}
                  min={0.01}
                  max={1000}
                  step={0.01}
                  className="flex-1 px-1 py-1 text-sm border rounded text-right border-gray-300"
                  title={t(`filaments:${field === 'alpha_s' ? 'alphaSHelp' : field === 'td_scale' ? 'tdScaleHelp' : 'tdGammaHelp'}`)}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default FilamentConfigPanel;
