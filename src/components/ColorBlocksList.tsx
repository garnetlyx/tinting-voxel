/**
 * Color blocks grid display component
 */
import { useTranslation } from '../i18n';
import React from 'react';
import type { ColorBlock } from '../api/types';

interface ColorBlocksListProps {
  colorBlocks: ColorBlock[];
}

export const ColorBlocksList: React.FC<ColorBlocksListProps> = ({ colorBlocks }) => {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
      {colorBlocks.map((color, index) => (
        <div
          key={index}
          className="rounded-sheet border border-rule bg-paper-raised p-1.5 transition-shadow hover:shadow-lift"
        >
          <div
            className="mb-2 h-20 w-full rounded-[2px]"
            style={{ backgroundColor: `rgb(${color.r},${color.g},${color.b})` }}
          />
          <div className="px-1.5 pb-1">
            <div className="font-mono text-[11px] text-ink">
              RGB({color.r},{color.g},{color.b})
            </div>
            <div className="text-[11px] text-ink-muted">
              {t('common:pixels', { count: color.count })}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
