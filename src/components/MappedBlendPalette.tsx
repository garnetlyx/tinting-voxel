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
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-800">{t('preview:mappedBlendPalette')}</h3>
        <p className="text-xs text-gray-500">{t('preview:mappingHelp')}</p>
      </div>

      <div className="space-y-2">
        {entries.map((entry, index) => (
          <div
            key={`${entry.code}-${entry.sourceHex}-${index}`}
            className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
          >
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div
                  className="h-6 w-6 rounded border border-gray-200"
                  style={{ backgroundColor: entry.sourceHex }}
                  title={t('preview:source', { hex: entry.sourceHex })}
                />
                <span className="text-xs text-gray-400">→</span>
                <div
                  className="h-6 w-6 rounded border border-gray-200"
                  style={{ backgroundColor: entry.hex }}
                  title={t('preview:printable', { hex: entry.hex })}
                />
              </div>
              <div>
                <div className="text-sm font-medium text-gray-800">{entry.code}</div>
                <div className="text-xs text-gray-500">
                  {t('preview:mapping', { source: entry.sourceHex, target: entry.hex })}
                </div>
              </div>
            </div>
            <div className="text-right text-xs text-gray-500">
              <div className="font-medium text-gray-700">{entry.pixelCount.toLocaleString()} px</div>
              <div>{entry.pixelPercent.toFixed(1)}%</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
