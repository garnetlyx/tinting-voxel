import { useTranslation } from '../i18n';
/**
 * Single row for editing one filament color configuration
 */
import React from 'react';
import { Trash2, Lock } from 'lucide-react';
import type { FilamentColorConfig } from '../api/types';

interface FilamentColorRowProps {
  config: FilamentColorConfig;
  index: number;
  onChange: (index: number, updated: FilamentColorConfig) => void;
  onRemove: (index: number) => void;
  canRemove: boolean;
  existingLabels: string[];
}

/** True when any measured field overrides the scalar td for this color. */
export const hasMeasuredParams = (config: FilamentColorConfig): boolean =>
  config.td_rgb != null || config.td_neutral != null;

/** Tooltip listing the parameters that actually drive blending/classification. */
export const measuredParamsDescription = (config: FilamentColorConfig): string => {
  const parts: string[] = [];
  if (config.td_rgb) parts.push(`td_rgb (${config.td_rgb.map(v => v.toFixed(2)).join(', ')})`);
  if (config.td_neutral != null) parts.push(`TD1S ${config.td_neutral}`);
  return parts.join(' · ');
};

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
  const isMeasured = hasMeasuredParams(config);

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

      {/* Transmission distance.
          Measured colors are locked: the scalar td is inert while td_rgb /
          td_neutral drive blending and classification, so editing it here
          would change nothing. The lock button downgrades the color to
          custom semantics (clears measured fields), after which this td
          drives both blending and the transparency fallback. */}
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
        disabled={isMeasured}
        min={0.1}
        max={1000}
        step={0.1}
        className={`w-20 px-2 py-1 text-sm border rounded text-right ${
          isMeasured ? 'border-gray-200 bg-gray-100 text-gray-400' : 'border-gray-300'
        }`}
        title={
          isMeasured
            ? `${measuredParamsDescription(config)}${config.transmission_distance ? `\n${t('filaments:measuredTdInert')}` : ''}`
            : t('filaments:transmissionDistanceMustBe0')
        }
      />

      {isMeasured && (
        <button
          onClick={() =>
            onChange(index, {
              ...config,
              td_rgb: undefined,
              td_neutral: undefined,
            })
          }
          className="p-1 rounded hover:bg-amber-50 transition-colors"
          title={t('filaments:downgradeToCustom')}
          aria-label={t('filaments:downgradeToCustom')}
        >
          <Lock className="w-4 h-4 text-amber-500" />
        </button>
      )}

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
