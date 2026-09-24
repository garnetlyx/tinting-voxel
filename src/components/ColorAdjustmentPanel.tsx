import { useTranslation } from '../i18n';
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
  const { t } = useTranslation();
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
    <section>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="tv-heading text-xl">
          {t('preview:colorBlocks', { count: colorBlocks.length })}
        </h2>
        {mergeSource !== null && (
          <div className="flex items-center gap-2 rounded-sheet border border-magenta/40 bg-magenta/5 px-3 py-1.5 text-sm text-magenta-deep">
            <Merge className="h-4 w-4" aria-hidden="true" />
            <span>{t('preview:selectTargetColorToMergeInto')}</span>
            <button
              aria-label={t('common:cancel')} onClick={handleCancelMerge}
              className="ml-1 rounded-sheet p-0.5 hover:bg-magenta/10"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
        {colorBlocks.map((color, index) => {
          const isSelected = selectedIndex === index;
          const isMergeSource = mergeSource === index;
          const isMergeTarget = mergeSource !== null && mergeSource !== index;
          const percentage = totalPixels > 0
            ? ((color.count / totalPixels) * 100).toFixed(1)
            : '0';

          const ariaLabel = t('preview:blockLabel', { hex: color.hex, count: color.count, percentage, state: [isSelected && t('preview:selected'), isMergeSource && t('preview:mergeSource'), isMergeTarget && t('preview:mergeTarget')].filter(Boolean).join('') });

          return (
            <div
              key={`${color.hex}-${color.count}-${color.r}-${color.g}-${color.b}`}
              role="button"
              tabIndex={0}
              aria-label={ariaLabel}
              aria-pressed={isSelected}
              onClick={() => handleSelect(index)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className={`cursor-pointer rounded-sheet border bg-paper-raised p-1.5 transition-all ${
                isMergeSource
                  ? 'border-magenta opacity-60 ring-2 ring-magenta/40'
                  : isMergeTarget
                    ? 'border-magenta/50 hover:border-magenta hover:ring-2 hover:ring-magenta/30'
                    : isSelected
                      ? 'border-ink shadow-lift ring-1 ring-ink'
                      : 'border-rule hover:border-ink/60 hover:shadow-lift'
              }`}
            >
              {/* Color swatch with inline color picker */}
              <div className="relative mb-2 h-20 w-full overflow-hidden rounded-[2px]">
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
                    title={t('preview:changeColor')}
                  />
                )}
              </div>

              {/* Color info */}
              <div className="px-1.5 pb-1">
                <div className="font-mono text-sm font-medium text-ink">
                  {color.hex.toUpperCase()}
                </div>
                <div className="font-mono text-[11px] text-ink-muted">
                  RGB({color.r},{color.g},{color.b})
                </div>
                <div className="mt-0.5 text-[11px] text-ink-muted">
                  {t('preview:pixelShare', { count: color.count, percentage })}
                </div>
              </div>

              {/* Action buttons (visible when selected) */}
              {isSelected && !isMergeSource && (
                <div
                  className="mt-1.5 flex gap-1 border-t border-rule pt-1.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => handleStartMerge(index)}
                    className="tv-btn-ghost tv-btn-sm flex-1 !px-1"
                    title={t('preview:mergeIntoAnotherColor')}
                  >
                    <Merge className="h-3 w-3" aria-hidden="true" />{t('preview:merge')}</button>
                  {colorBlocks.length > 1 && (
                    <button
                      onClick={() => handleDelete(index)}
                      className="tv-btn-ghost tv-btn-sm flex-1 !px-1 hover:!text-signal-error"
                      title={t('preview:deleteAndMergeIntoNearestColor')}
                    >
                      <Trash2 className="h-3 w-3" aria-hidden="true" />{t('common:delete')}</button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
