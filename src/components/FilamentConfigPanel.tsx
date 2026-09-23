import { useTranslation } from '../i18n';
import React from 'react';
import { Plus } from 'lucide-react';
import type { FilamentPreset, FilamentColorConfig, FilamentPresetInfo } from '../api/types';
import { PresetSelector } from './PresetSelector';
import { FilamentColorRow } from './FilamentColorRow';

const MAX_FILAMENT_COLORS = 16;
const MIN_FILAMENT_COLORS = 4;

interface FilamentConfigPanelProps {
  presets: FilamentPresetInfo[];
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
  presets,
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
  const canAdd = filamentColors.length < MAX_FILAMENT_COLORS;
  const canRemove = filamentColors.length > MIN_FILAMENT_COLORS;

  return (
    <div className="space-y-3">
      <PresetSelector
        presets={presets}
        selectedPreset={filamentPreset}
        onPresetChange={onLoadPreset}
        disabled={disabled}
      />
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 font-medium">
            {t('filaments:capacity', { count: filamentColors.length, max: MAX_FILAMENT_COLORS })}
          </span>
          {!isValid && (
            <span className="text-xs text-red-500 font-medium">{t('filaments:fixValidationErrorsBelow')}</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400 px-0.5">
          <span className="w-8">{t('filaments:hex')}</span>
          <span className="flex-1">{t('filaments:codeName')}</span>
          <span className="w-36"><span className="inline-block w-20 text-right">{t('filaments:td')}</span></span>
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
          />
        ))}
      </div>
      <button
        onClick={onAddColor}
        disabled={!canAdd || disabled}
        className="flex items-center gap-1 text-sm text-purple-600 hover:text-purple-800 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        <Plus className="w-4 h-4" />{t('filaments:addColor')}</button>
    </div>
  );
};

export default FilamentConfigPanel;
