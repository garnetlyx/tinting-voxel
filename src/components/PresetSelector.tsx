/**
 * Filament preset selector component
 */
import React from 'react';
import type { FilamentPreset } from '../api/types';
import { DEFAULT_PRESETS } from '../api/types';

interface PresetSelectorProps {
  selectedPreset: FilamentPreset | null;
  onPresetChange: (preset: FilamentPreset) => void;
  disabled?: boolean;
}

const PRESET_OPTIONS: { value: FilamentPreset | null; label: string }[] = [
  { value: null, label: 'Custom' },
  { value: 'bambu_cmyk', label: 'Bambu CMYK' },
  { value: 'bambu_cmyk_calibrated', label: 'Bambu CMYK Calibrated' },
  { value: 'clear_cmyk', label: 'Clear CMYK' },
];

export const PresetSelector: React.FC<PresetSelectorProps> = ({
  selectedPreset,
  onPresetChange,
  disabled = false,
}) => {
  // Handle null case for custom colors
  const currentValue = selectedPreset ?? 'custom';

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Filament Preset
        </label>
        <select
          value={currentValue}
          onChange={(e) => {
            const value = e.target.value;
            if (value === 'custom') {
              // User selected "Custom" - do nothing (already in custom mode)
              // The parent component handles the null case
              return;
            }
            onPresetChange(value as FilamentPreset);
          }}
          disabled={disabled}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-gray-100"
        >
          {PRESET_OPTIONS.map((option) => (
            <option key={option.value ?? 'custom'} value={option.value ?? 'custom'}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Color preview - only show for presets, not custom */}
      {selectedPreset && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Colors:</span>
          <div className="flex gap-1">
            {DEFAULT_PRESETS[selectedPreset].map((color, index) => (
              <div
                key={index}
                className="w-6 h-6 rounded border border-gray-200 shadow-sm"
                style={{ backgroundColor: color.hex }}
                title={`${color.name} (TD: ${color.transmission_distance})`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PresetSelector;
