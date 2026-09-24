import { useTranslation } from '../i18n';
import React from 'react';
import type { MappedBlendPaletteEntry } from '../api/types';

interface MappedBlendPaletteProps {
  entries: MappedBlendPaletteEntry[];
}

export const MappedBlendPalette: React.FC<MappedBlendPaletteProps> = ({ entries }) => {
  const { t } = useTranslation();
  if (entries.length === 0) return null;

  return (
    <section>
      <h2 className="tv-heading mb-3">{t('preview:mappedBlendPalette')}</h2>
      <div className="grid gap-x-6 sm:grid-cols-2 2xl:grid-cols-3">
        {entries.map((entry, index) => (
          <div
            key={`${entry.code}-${entry.sourceHex}-${index}`}
            className="flex items-center justify-between gap-3 border-b border-rule py-2"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex shrink-0 items-center">
                <div
                  className="h-7 w-7 border border-ink/30"
                  style={{ backgroundColor: entry.sourceHex }}
                  title={t('preview:source', { hex: entry.sourceHex })}
                />
                <span className="px-1 text-xs text-ink-muted" aria-hidden="true">→</span>
                <div
                  className="h-7 w-7 border border-ink/30"
                  style={{ backgroundColor: entry.hex }}
                  title={t('preview:printable', { hex: entry.hex })}
                />
              </div>
              <div className="min-w-0">
                <div className="truncate font-mono text-sm font-medium text-ink">{entry.code}</div>
                <div className="truncate font-mono text-[11px] text-ink-muted">
                  {t('preview:mapping', { source: entry.sourceHex, target: entry.hex })}
                </div>
              </div>
            </div>
            <div className="shrink-0 text-right font-mono text-xs text-ink-muted">
              <div className="text-ink">{entry.pixelPercent.toFixed(1)}%</div>
              <div>{entry.pixelCount.toLocaleString()} px</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
