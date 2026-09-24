/**
 * Vector color list display component for SVG mode
 */
import { useTranslation } from '../i18n';
import React from 'react';
import type { VectorColorResult } from '../api/types';

interface VectorColorListProps {
  vectorResults: VectorColorResult[];
}

export const VectorColorList: React.FC<VectorColorListProps> = ({ vectorResults }) => {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
      {vectorResults.map((result, index) => {
        const regionCount = result.regions.length;
        const holeCount = result.regions.reduce((sum, region) => sum + region.holes.length, 0);

        return (
        <div
          key={index}
          className="rounded-sheet border border-rule bg-paper-raised p-1.5 transition-shadow hover:shadow-lift"
        >
          <div
            className="mb-2 h-20 w-full rounded-[2px]"
            style={{ backgroundColor: `rgb(${result.color[0]},${result.color[1]},${result.color[2]})` }}
          />
          <div className="px-1.5 pb-1">
            <div className="font-mono text-[11px] text-ink">
              RGB({result.color[0]},{result.color[1]},{result.color[2]})
            </div>
            <div className="text-[11px] text-ink-muted">
              {t('preview:vertices', { count: result.polygon_points })}
            </div>
            <div className="text-[11px] text-ink-muted">
              {t('preview:regions', { count: regionCount })}{holeCount > 0 ? t('preview:holes', { count: holeCount }) : ''}
            </div>
          </div>
        </div>
        );
      })}
    </div>
  );
};
