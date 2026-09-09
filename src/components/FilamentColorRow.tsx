import { useTranslation } from '../i18n';
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
  const { t } = useTranslation();
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
        title={t('filaments:pickColor')}
      />

      {/* Stable code editor; existing canonical names remain unchanged until edited. */}
      <div className="flex-1 min-w-0">
        <input
          type="text"
          value={label}
          maxLength={1}
          onChange={(e) => {
            const code = e.target.value.toUpperCase();
            if (/^[A-Z]?$/.test(code)) onChange(index, { ...config, name: code });
          }}
          title={isDuplicate ? t('filaments:duplicateLabel') : t('filaments:label', { code: label })}
          aria-invalid={Boolean(isDuplicate || isEmptyName)}
          placeholder={t('filaments:codeName')}
          aria-label={t('common:colorEntry', { index: index + 1, code: label || '?', hex: config.hex })}
          className={`w-full px-2 py-1 text-sm border rounded ${
            isDuplicate || isEmptyName ? 'border-red-400 bg-red-50' : 'border-gray-300'
          }`}
        />
      </div>

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
        title={t('filaments:transmissionDistanceMustBe0')}
      />

      {/* Remove button */}
      <button
        onClick={() => onRemove(index)}
        disabled={!canRemove}
        className="p-1 rounded hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        title={canRemove ? t('filaments:removeColor') : t('filaments:minimum4ColorsRequired')}
      >
        <Trash2 className="w-4 h-4 text-red-500" />
      </button>
    </div>
  );
};

export default FilamentColorRow;
