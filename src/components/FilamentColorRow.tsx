/**
 * Single row for editing one filament color configuration
 */
import React from 'react';
import { Trash2 } from 'lucide-react';
import type { FilamentColorConfig } from '../api/types';

interface FilamentColorRowProps {
  config: FilamentColorConfig;
  index: number;
  onChange: (index: number, updated: FilamentColorConfig) => void;
  onRemove: (index: number) => void;
  canRemove: boolean;
  existingLabels: string[];
}

export const FilamentColorRow: React.FC<FilamentColorRowProps> = ({
  config,
  index,
  onChange,
  onRemove,
  canRemove,
  existingLabels,
}) => {
  const label = config.name?.[0]?.toUpperCase() ?? '';
  const isDuplicate = label && existingLabels.filter(l => l === label).length > 1;
  const isEmptyName = !config.name.trim();

  return (
    <div className="flex items-center gap-2">
      {/* Color picker */}
      <input
        type="color"
        value={config.hex}
        onChange={(e) => onChange(index, { ...config, hex: e.target.value })}
        className="w-8 h-8 rounded border border-gray-300 cursor-pointer p-0"
        title="Pick color"
      />

      {/* Name input */}
      <div className="flex-1 min-w-0">
        <input
          type="text"
          value={config.name}
          onChange={(e) => onChange(index, { ...config, name: e.target.value })}
          placeholder="Color name"
          className={`w-full px-2 py-1 text-sm border rounded ${
            isDuplicate || isEmptyName ? 'border-red-400 bg-red-50' : 'border-gray-300'
          }`}
        />
      </div>

      {/* Label badge */}
      <span
        className={`w-6 h-6 flex items-center justify-center text-xs font-bold rounded ${
          isDuplicate ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600'
        }`}
        title={isDuplicate ? 'Duplicate label' : `Label: ${label}`}
      >
        {label || '?'}
      </span>

      {/* Transmission distance */}
      <input
        type="number"
        value={config.transmission_distance}
        onChange={(e) => {
          const val = parseFloat(e.target.value);
          // Allow any valid number including 0 (for intermediate input like "0.5")
          // The > 0 validation is done at form level (isFilamentConfigValid)
          if (!isNaN(val) && val >= 0 && val <= 1000) {
            onChange(index, { ...config, transmission_distance: val });
          }
        }}
        min={0.1}
        max={1000}
        step={0.1}
        className="w-20 px-2 py-1 text-sm border border-gray-300 rounded text-right"
        title="Transmission distance (must be > 0)"
      />

      {/* Remove button */}
      <button
        onClick={() => onRemove(index)}
        disabled={!canRemove}
        className="p-1 rounded hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        title={canRemove ? 'Remove color' : 'Minimum 4 colors required'}
      >
        <Trash2 className="w-4 h-4 text-red-500" />
      </button>
    </div>
  );
};

export default FilamentColorRow;
