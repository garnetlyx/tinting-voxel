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
    <div className="space-y-1 border-b border-rule/60 pb-1.5 last:border-b-0">
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={config.hex}
          onChange={(e) => onChange(index, { ...config, hex: e.target.value })}
          className="h-8 w-8 cursor-pointer rounded-[2px] border border-ink/50 bg-transparent p-0"
          title={t('filaments:pickColor')}
        />
        <span className="min-w-0 flex-1 px-2 font-mono text-sm font-medium" title={t('filaments:label', { code: label })}>
          {label}
        </span>
        <div className="flex w-40 items-center gap-1">
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
            className="w-24 rounded-sheet border border-rule-strong bg-paper-raised px-2 py-1 text-right font-mono text-sm focus:border-ink focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setShowChannels((visible) => !visible)}
            aria-expanded={showChannels}
            aria-controls={channelsId}
            className="rounded-sheet px-1.5 py-1 font-mono text-xs text-ink-soft transition-colors hover:bg-paper-sunk hover:text-ink aria-expanded:bg-ink aria-expanded:text-paper-raised"
          >
            {t('filaments:rgb')}
          </button>
        </div>
        <button
          type="button"
          onClick={() => onRemove(index)}
          disabled={!canRemove}
          className="rounded-sheet p-1 text-ink-muted transition-colors hover:bg-signal-error/10 hover:text-signal-error disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent"
          title={canRemove ? t('filaments:removeColor') : t('filaments:minimum4ColorsRequired')}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      {showChannels && (
        <div id={channelsId} className="flex justify-end gap-2 pr-8 font-mono text-xs text-ink-muted">
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
                className="w-16 rounded-sheet border border-rule-strong bg-paper-raised px-1 py-1 text-right focus:border-ink focus:outline-none"
              />
            </label>
          ))}
        </div>
      )}
    </div>
  );
};

export default FilamentColorRow;
