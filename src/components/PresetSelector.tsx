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
      <label className="block text-sm font-medium text-gray-700 mb-2">{t('filaments:filamentPreset')}</label>
      <select
        aria-label={t('filaments:filamentPreset')}
        value={selectedPreset ?? ''}
        onChange={(e) => onPresetChange(e.target.value as FilamentPreset)}
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-gray-100"
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
