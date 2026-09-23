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
  const selected = presets.find((preset) => preset.name === selectedPreset);

  return (
    <div className="space-y-3">
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
      {selected && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{t('filaments:colors')}</span>
          <div className="flex gap-1">
            {selected.colors.map((color, index) => (
              <div
                key={color.name}
                className="w-6 h-6 rounded border border-gray-200 shadow-sm"
                style={{ backgroundColor: color.hex }}
                title={t('common:colorEntry', { index: index + 1, code: color.name[0]?.toUpperCase() ?? '?', hex: color.hex })}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PresetSelector;
