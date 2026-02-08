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
            {filamentColors.length} of {MAX_FILAMENT_COLORS} colors
          </span>
          {!isValid && (
            <span className="text-xs text-red-500 font-medium">
              Fix validation errors below
            </span>
          )}
        </div>

        {/* Column headers */}
        <div className="flex items-center gap-2 text-xs text-gray-400 px-0.5">
          <span className="w-8">Hex</span>
          <span className="flex-1">Name</span>
          <span className="w-6 text-center">ID</span>
          <span className="w-20 text-right">TD</span>
          <span className="w-6"></span>
        </div>

        {filamentColors.map((config, index) => (
          <FilamentColorRow
            key={`${config.name}-${config.hex}-${config.transmission_distance}`}
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
        <Plus className="w-4 h-4" />
        Add Color
      </button>
    </div>
  );
};

export default FilamentConfigPanel;
