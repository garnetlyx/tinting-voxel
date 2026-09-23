import React, { useId, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { useTranslation } from '../i18n';
import type { FilamentColorConfig, TransmissionDistance } from '../api/types';

interface FilamentColorRowProps {
  config: FilamentColorConfig;
  index: number;
  onChange: (index: number, updated: FilamentColorConfig) => void;
  onRemove: (index: number) => void;
  canRemove: boolean;
}

export const FilamentColorRow: React.FC<FilamentColorRowProps> = ({
  config,
  index,
  onChange,
  onRemove,
  canRemove,
}) => {
  const { t } = useTranslation();
  const [showChannels, setShowChannels] = useState(false);
  const channelsId = useId();
  const label = config.name[0]?.toUpperCase() ?? '';
  const td = config.transmission_distance;
  const channels: [number, number, number] = Array.isArray(td) ? td : [td, td, td];
  const displayedTd = Array.isArray(td) ? Number((td.reduce((sum, value) => sum + value, 0) / td.length).toPrecision(4)) : td;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={config.hex}
          onChange={(e) => onChange(index, { ...config, hex: e.target.value })}
          className="w-8 h-8 rounded border border-gray-300 cursor-pointer p-0"
          title={t('filaments:pickColor')}
        />
        <span className="flex-1 min-w-0 px-2 text-sm" title={t('filaments:label', { code: label })}>
          {label}
        </span>
        <div className="w-36 flex items-center gap-1">
          <input
            type="number"
            aria-label={t('filaments:tdEntry', { index: index + 1 })}
            value={displayedTd || ''}
            onChange={(e) => {
              const value = e.target.value === '' ? 0 : parseFloat(e.target.value);
              if (!isNaN(value) && value >= 0 && value <= 1000) {
                onChange(index, { ...config, transmission_distance: value });
              }
            }}
            min={0}
            max={1000}
            step="any"
            className="w-20 px-2 py-1 text-sm border rounded text-right border-gray-300"
          />
          <button
            type="button"
            onClick={() => setShowChannels((visible) => !visible)}
            aria-expanded={showChannels}
            aria-controls={channelsId}
            className="px-1 py-1 text-xs text-purple-600 hover:text-purple-800 rounded"
          >
            {t('filaments:rgb')}
          </button>
        </div>
        <button
          type="button"
          onClick={() => onRemove(index)}
          disabled={!canRemove}
          className="p-1 rounded hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title={canRemove ? t('filaments:removeColor') : t('filaments:minimum4ColorsRequired')}
        >
          <Trash2 className="w-4 h-4 text-red-500" />
        </button>
      </div>
      {showChannels && (
        <div id={channelsId} className="flex justify-end gap-2 pr-8 text-xs text-gray-500">
          {channels.map((value, channel) => (
            <label key={channel} className="flex items-center gap-1">
              {'RGB'[channel]}
              <input
                type="number"
                aria-label={t('filaments:tdChannel', { index: index + 1, channel: 'RGB'[channel] })}
                value={value || ''}
                min={0}
                max={1000}
                step="any"
                onChange={(e) => {
                  const updated = e.target.value === '' ? 0 : parseFloat(e.target.value);
                  if (!isNaN(updated) && updated >= 0 && updated <= 1000) {
                    const next: TransmissionDistance = [...channels];
                    next[channel] = updated;
                    onChange(index, { ...config, transmission_distance: next });
                  }
                }}
                className="w-16 rounded border border-gray-300 px-1 py-1 text-right"
              />
            </label>
          ))}
        </div>
      )}
    </div>
  );
};

export default FilamentColorRow;
