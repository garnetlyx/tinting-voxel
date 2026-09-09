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
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
      {colorBlocks.map((color, index) => (
        <div
          key={index}
          className="border rounded-lg p-3 hover:shadow-lg transition-shadow"
        >
          <div
            className="w-full h-20 rounded-md mb-2"
            style={{ backgroundColor: `rgb(${color.r},${color.g},${color.b})` }}
          />
          <div className="text-xs text-gray-600 mb-1">
            RGB({color.r},{color.g},{color.b})
          </div>
          <div className="text-xs text-gray-500 mb-2">
            {t('common:pixels', { count: color.count })}
          </div>
        </div>
      ))}
    </div>
  );
};
