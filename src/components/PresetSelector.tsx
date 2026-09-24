import React from 'react';
import { usePresetLabel } from '../i18n/catalog';
import { useTranslation } from '../i18n';
import type { FilamentPreset, FilamentPresetInfo } from '../api/types';

interface PresetSelectorProps {
  presets: FilamentPresetInfo[];
  selectedPreset: FilamentPreset | null;
  onPresetChange: (preset: FilamentPreset) => void;
  disabled?: boolean;
}

export const PresetSelector: React.FC<PresetSelectorProps> = ({
  presets,
  selectedPreset,
  onPresetChange,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const presetLabel = usePresetLabel();

  return (
    <div>
      <label htmlFor="filament-preset" className="text-sm font-medium text-ink-soft">{t('filaments:filamentPreset')}</label>
      <select
        id="filament-preset"
        aria-label={t('filaments:filamentPreset')}
        value={selectedPreset ?? ''}
        onChange={(e) => onPresetChange(e.target.value as FilamentPreset)}
        disabled={disabled}
        className="tv-select mt-1.5"
      >
        {selectedPreset === null && <option value="" disabled>{t('filaments:custom')}</option>}
        {presets.map((preset) => (
          <option key={preset.name} value={preset.name}>
            {presetLabel(preset.name, preset.display_name)}
          </option>
        ))}
      </select>
    </div>
  );
};

export default PresetSelector;
