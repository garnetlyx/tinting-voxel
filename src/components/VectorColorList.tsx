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
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
      {vectorResults.map((result, index) => {
        const regionCount = result.regions?.length ?? result.polygons.length;
        const holeCount = result.regions?.reduce((sum, region) => sum + region.holes.length, 0) ?? 0;

        return (
        <div
          key={index}
          className="border rounded-lg p-3 hover:shadow-lg transition-shadow"
        >
          <div
            className="w-full h-20 rounded-md mb-2"
            style={{ backgroundColor: `rgb(${result.color[0]},${result.color[1]},${result.color[2]})` }}
          />
          <div className="text-xs text-gray-600 mb-1">
            RGB({result.color[0]},{result.color[1]},{result.color[2]})
          </div>
          <div className="text-xs text-gray-500">
            {t('preview:vertices', { count: result.polygon_points })}
          </div>
          <div className="text-xs text-gray-500">
            {t('preview:regions', { count: regionCount })}{holeCount > 0 ? t('preview:holes', { count: holeCount }) : ''}
          </div>
        </div>
        );
      })}
    </div>
  );
};
