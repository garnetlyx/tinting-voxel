/**
 * Manual color adjustment panel for reassigning color block mappings.
 * Allows users to edit colors, merge blocks, and delete blocks.
 */
import React, { useState, useEffect } from 'react';
import { Trash2, Merge, X } from 'lucide-react';
import type { ColorBlock } from '../api/types';

interface ColorAdjustmentPanelProps {
  colorBlocks: ColorBlock[];
  onUpdateColor: (index: number, hex: string) => void;
  onMergeColors: (sourceIndex: number, targetIndex: number) => void;
  onDeleteColor: (index: number) => void;
}

export const ColorAdjustmentPanel: React.FC<ColorAdjustmentPanelProps> = ({
  colorBlocks,
  onUpdateColor,
  onMergeColors,
  onDeleteColor,
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [mergeSource, setMergeSource] = useState<number | null>(null);

  // Reset selection when colorBlocks array changes externally (merge/delete from parent)
  useEffect(() => {
    setSelectedIndex(null);
    setMergeSource(null);
  }, [colorBlocks.length]);

  const handleColorChange = (index: number, hex: string) => {
    onUpdateColor(index, hex);
  };

  const handleStartMerge = (index: number) => {
    setMergeSource(index);
    setSelectedIndex(null);
  };

  const handleMergeTarget = (targetIndex: number) => {
    if (mergeSource !== null && mergeSource !== targetIndex) {
      onMergeColors(mergeSource, targetIndex);
      setMergeSource(null);
      setSelectedIndex(null);
    }
  };

  const handleCancelMerge = () => {
    setMergeSource(null);
  };

  const handleDelete = (index: number) => {
    if (colorBlocks.length <= 1) return;
    onDeleteColor(index);
    setSelectedIndex(null);
    // Adjust mergeSource if needed
    if (mergeSource !== null) {
      if (mergeSource === index) {
        setMergeSource(null);
      } else if (mergeSource > index) {
        setMergeSource(mergeSource - 1);
      }
    }
  };

  const handleSelect = (index: number) => {
    if (mergeSource !== null) {
      handleMergeTarget(index);
      return;
    }
    setSelectedIndex(selectedIndex === index ? null : index);
  };

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSelect(index);
    }
  };

  const totalPixels = colorBlocks.reduce((sum, b) => sum + b.count, 0);

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800">
          Color Blocks ({colorBlocks.length})
        </h2>
        {mergeSource !== null && (
          <div className="flex items-center gap-2 text-sm text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg">
            <Merge className="w-4 h-4" />
            <span>Select target color to merge into</span>
            <button
              onClick={handleCancelMerge}
              className="ml-1 p-0.5 hover:bg-blue-100 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {colorBlocks.map((color, index) => {
          const isSelected = selectedIndex === index;
          const isMergeSource = mergeSource === index;
          const isMergeTarget = mergeSource !== null && mergeSource !== index;
          const percentage = totalPixels > 0
            ? ((color.count / totalPixels) * 100).toFixed(1)
            : '0';

          const ariaLabel = `Color block ${color.hex}, ${color.count} pixels, ${percentage}%${isSelected ? ', selected' : ''}${isMergeSource ? ', merge source' : ''}${isMergeTarget ? ', click to merge' : ''}`;

          return (
            <div
              key={`${color.hex}-${color.count}-${color.r}-${color.g}-${color.b}`}
              role="button"
              tabIndex={0}
              aria-label={ariaLabel}
              aria-pressed={isSelected}
              onClick={() => handleSelect(index)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className={`border rounded-lg p-3 transition-all cursor-pointer ${
                isMergeSource
                  ? 'border-blue-500 ring-2 ring-blue-300 opacity-60'
                  : isMergeTarget
                    ? 'border-blue-400 hover:border-blue-500 hover:ring-2 hover:ring-blue-300'
                    : isSelected
                      ? 'border-purple-500 ring-2 ring-purple-300 shadow-lg'
                      : 'border-gray-200 hover:shadow-lg hover:border-gray-300'
              }`}
            >
              {/* Color swatch with inline color picker */}
              <div className="relative w-full h-20 rounded-md mb-2 overflow-hidden">
                <div
                  className="w-full h-full"
                  style={{ backgroundColor: `rgb(${color.r},${color.g},${color.b})` }}
                />
                {isSelected && (
                  <input
                    type="color"
                    value={color.hex}
                    onChange={(e) => handleColorChange(index, e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    title="Change color"
                  />
                )}
              </div>

              {/* Color info */}
              <div className="text-xs text-gray-600 mb-0.5 font-mono">
                {color.hex.toUpperCase()}
              </div>
              <div className="text-xs text-gray-500 mb-0.5">
                RGB({color.r},{color.g},{color.b})
              </div>
              <div className="text-xs text-gray-400">
                {color.count} px ({percentage}%)
              </div>

              {/* Action buttons (visible when selected) */}
              {isSelected && !isMergeSource && (
                <div
                  className="flex gap-1 mt-2 pt-2 border-t border-gray-100"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => handleStartMerge(index)}
                    className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs text-blue-600 bg-blue-50 hover:bg-blue-100 rounded transition-colors"
                    title="Merge into another color"
                  >
                    <Merge className="w-3 h-3" />
                    Merge
                  </button>
                  {colorBlocks.length > 1 && (
                    <button
                      onClick={() => handleDelete(index)}
                      className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs text-red-600 bg-red-50 hover:bg-red-100 rounded transition-colors"
                      title="Delete and merge into nearest color"
                    >
                      <Trash2 className="w-3 h-3" />
                      Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {colorBlocks.length > 0 && (
        <p className="mt-3 text-xs text-gray-400">
          Click a color to edit it. Use merge to combine two colors, or delete to remove one.
        </p>
      )}
    </div>
  );
};
