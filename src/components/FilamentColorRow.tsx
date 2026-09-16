import { useTranslation } from '../i18n';
/**
 * Single row for editing one filament color configuration
 */
import React from 'react';
import { Trash2, ChevronsUpDown } from 'lucide-react';
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

      {/* Transmission distance — the one composite TD this color carries;
          it drives blending, classification, everything. Per-channel
          staircase TDs (R/G/B) when the color carries them. */}
      {config.td_rgb ? (
        <div className="flex gap-1">
          {([0, 1, 2] as const).map((ch) => {
            const channels = config.td_rgb!;
            return (
            <input
              key={ch}
              type="number"
              aria-label={t('filaments:tdRgbEntry', { index: index + 1, channel: 'RGB'[ch] })}
              value={channels[ch]}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val > 0 && val <= 1000) {
                  const next = [...channels];
                  next[ch] = val;
                  onChange(index, { ...config, td_rgb: next });
                }
              }}
              min={0.1}
              max={1000}
              step={0.1}
              className="w-14 px-1 py-1 text-sm border rounded text-right border-gray-300"
              title={t('filaments:tdRgbHelp')}
            />
            );
          })}
        </div>
      ) : (
        <input
          type="number"
          aria-label={t('filaments:tdEntry', { index: index + 1 })}
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
          className="w-20 px-2 py-1 text-sm border rounded text-right border-gray-300"
          title={t('filaments:transmissionDistanceMustBe0')}
        />
      )}

      {/* Toggle scalar / per-channel td. */}
      <button
        type="button"
        onClick={() => {
          if (config.td_rgb) {
            // Collapse: keep the channel mean as the scalar td.
            const mean = config.td_rgb.reduce((a, b) => a + b, 0) / config.td_rgb.length;
            const { td_rgb: _drop, ...rest } = config;
            onChange(index, { ...rest, transmission_distance: mean });
          } else {
            onChange(index, {
              ...config,
              td_rgb: [config.transmission_distance, config.transmission_distance, config.transmission_distance],
            });
          }
        }}
        className="p-1 text-gray-400 hover:text-gray-600"
        title={config.td_rgb ? t('filaments:tdPerChannelOff') : t('filaments:tdPerChannelOn')}
        aria-label={config.td_rgb ? t('filaments:tdPerChannelOff') : t('filaments:tdPerChannelOn')}
      >
        <ChevronsUpDown size={14} />
      </button>

      {/* Optional pigment absorption gain. Calibrated presets carry a
          fitted value; 0 (or cleared) blends as plain Beer-Lambert. */}
      <input
        type="number"
        aria-label={t('filaments:kEntry', { index: index + 1 })}
        value={config.k ?? 0}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === '') {
            onChange(index, { ...config, k: 0 });
            return;
          }
          const val = parseFloat(raw);
          if (!isNaN(val) && val >= 0 && val <= 1000) {
            onChange(index, { ...config, k: val });
          }
        }}
        min={0}
        max={1000}
        step={0.01}
        className="w-16 px-2 py-1 text-sm border rounded text-right border-gray-300"
        title={t('filaments:kHelp')}
      />

      {/* Scalar-form capture compensation (paper Eqs. (1)-(2)); shown only
          for scalar-td colors — per-channel staircase colors don't use it. */}
      {!config.td_rgb && (
        <>
          <input
            type="number"
            aria-label={t('filaments:alphaSEntry', { index: index + 1 })}
            value={config.alpha_s ?? 2.302585092994046}
            onChange={(e) => {
              const raw = e.target.value;
              const val = raw === '' ? 2.302585092994046 : parseFloat(raw);
              if (!isNaN(val) && val > 0 && val <= 1000) {
                onChange(index, { ...config, alpha_s: val });
              }
            }}
            min={0.01}
            max={1000}
            step={0.01}
            className="w-16 px-2 py-1 text-sm border rounded text-right border-gray-300"
            title={t('filaments:alphaSHelp')}
          />
          <input
            type="number"
            aria-label={t('filaments:tdScaleEntry', { index: index + 1 })}
            value={config.td_scale ?? 1}
            onChange={(e) => {
              const raw = e.target.value;
              const val = raw === '' ? 1 : parseFloat(raw);
              if (!isNaN(val) && val > 0 && val <= 1000) {
                onChange(index, { ...config, td_scale: val });
              }
            }}
            min={0.01}
            max={1000}
            step={0.01}
            className="w-16 px-2 py-1 text-sm border rounded text-right border-gray-300"
            title={t('filaments:tdScaleHelp')}
          />
          <input
            type="number"
            aria-label={t('filaments:tdGammaEntry', { index: index + 1 })}
            value={config.td_gamma ?? 1}
            onChange={(e) => {
              const raw = e.target.value;
              const val = raw === '' ? 1 : parseFloat(raw);
              if (!isNaN(val) && val > 0 && val <= 1000) {
                onChange(index, { ...config, td_gamma: val });
              }
            }}
            min={0.01}
            max={1000}
            step={0.01}
            className="w-16 px-2 py-1 text-sm border rounded text-right border-gray-300"
            title={t('filaments:tdGammaHelp')}
          />
        </>
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
