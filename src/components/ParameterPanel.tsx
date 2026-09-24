import { useTranslation } from '../i18n';
/**
 * Print parameters, grouped into numbered sections of the settings rail
 */
import React, { useEffect, useId, useState } from 'react';
import { RefreshCw, SlidersHorizontal } from 'lucide-react';
import type { FilamentColorConfig, PrintStackInfo, ProcessingMode } from '../api/types';
import { LAYER_HEIGHT_MIN_MM, LAYER_HEIGHT_MAX_MM } from '../api/types';
import { ModeSelector } from './ModeSelector';
import { RailSection } from './RailSection';
import { RangeField } from './RangeField';
import { filamentLabel } from '../utils/filaments';

const DETAIL_SIZES_MM = [0.22, 0.42, 0.62, 0.82];

interface ParameterPanelProps {
  mode: ProcessingMode;
  onModeChange: (mode: ProcessingMode) => void;
  // Pixel mode params
  maxColors: number;
  colorThreshold: number;
  onMaxColorsChange: (value: number) => void;
  onColorThresholdChange: (value: number) => void;
  // SVG mode params
  epsilon: number;
  minArea: number;
  numColors: number;
  onEpsilonChange: (value: number) => void;
  onMinAreaChange: (value: number) => void;
  onNumColorsChange: (value: number) => void;
  // Shared params
  layerHeight: number;
  layerCount: number;
  maxLayerCount: number;
  /** Most colors a request may use (served by the backend). */
  maxTargetColors?: number;
  pixelSize: number;
  onLayerHeightChange: (value: number) => void;
  onLayerCountChange: (value: number) => void;
  onPixelSizeChange: (value: number) => void;
  // Detail size
  detailSize: number;
  onDetailSizeChange: (value: number) => void;
  // Target physical size
  targetWidth: number;
  targetHeight: number;
  maxDimension: number;
  onMaxDimensionChange: (value: number) => void;
  whiteBackingLayers: number;
  onWhiteBackingLayersChange: (value: number) => void;
  /** The current filament set; one of them is printed as the backing block. */
  filamentColors: FilamentColorConfig[];
  backingFilament?: string;
  onBackingFilamentChange: (label: string) => void;
  printStack: PrintStackInfo;
  onReprocess: () => void;
  processing: boolean;
  hasImage: boolean;
  onAutoOptimize?: () => void;
}

/** Color layers over backing layers, drawn as the stack prints (top first). */
const StackDiagram: React.FC<{ stack: PrintStackInfo; backingHex?: string }> = ({ stack, backingHex }) => (
  <div aria-hidden="true" className="flex w-16 shrink-0 flex-col gap-px">
    {Array.from({ length: stack.opticalLayerCount }, (_, i) => (
      <span
        key={`c${i}`}
        className="block h-1.5"
        style={{ background: 'repeating-linear-gradient(135deg, rgb(var(--cyan)) 0 3px, rgb(var(--magenta)) 3px 6px, rgb(var(--yellow)) 6px 9px)' }}
      />
    ))}
    {Array.from({ length: stack.whiteBackingLayers }, (_, i) => (
      <span
        key={`b${i}`}
        className="block h-1.5 border border-ink/25"
        style={{ background: backingHex }}
      />
    ))}
  </div>
);

export const ParameterPanel: React.FC<ParameterPanelProps> = ({
  mode,
  onModeChange,
  maxColors,
  colorThreshold,
  onMaxColorsChange,
  onColorThresholdChange,
  epsilon,
  minArea,
  numColors,
  onEpsilonChange,
  onMinAreaChange,
  onNumColorsChange,
  layerHeight,
  layerCount,
  maxLayerCount,
  maxTargetColors,
  pixelSize,
  onLayerHeightChange,
  onLayerCountChange,
  onPixelSizeChange,
  detailSize,
  onDetailSizeChange,
  targetWidth,
  targetHeight,
  maxDimension,
  onMaxDimensionChange,
  whiteBackingLayers,
  onWhiteBackingLayersChange,
  filamentColors,
  backingFilament,
  onBackingFilamentChange,
  printStack,
  onReprocess,
  processing,
  hasImage,
  onAutoOptimize,
}) => {
  const { t } = useTranslation();
  const detailSizeLabelId = useId();
  const backingFilamentLabelId = useId();
  const formatMaxDimension = (value: number) => value.toFixed(1);
  const [maxDimensionInput, setMaxDimensionInput] = useState(formatMaxDimension(maxDimension));
  const [isEditingMaxDimension, setIsEditingMaxDimension] = useState(false);

  useEffect(() => {
    if (!isEditingMaxDimension) {
      setMaxDimensionInput(formatMaxDimension(maxDimension));
    }
  }, [isEditingMaxDimension, maxDimension]);

  const commitMaxDimension = () => {
    setIsEditingMaxDimension(false);
    const parsed = parseFloat(maxDimensionInput);
    if (!Number.isFinite(parsed)) {
      setMaxDimensionInput(formatMaxDimension(maxDimension));
      return;
    }
    onMaxDimensionChange(parsed);
  };

  return (
    <>
      <RailSection index={1} title={t('parameters:processingMode')}>
        <ModeSelector mode={mode} onModeChange={onModeChange} disabled={processing} />
      </RailSection>

      <RailSection index={2} title={t('converter:sectionColor')}>
        {mode === 'pixel' ? (
          <>
            <RangeField
              label={t('parameters:maxColors')}
              display={String(maxColors)}
              value={maxColors}
              min={2}
              max={maxTargetColors ?? 100}
              onChange={onMaxColorsChange}
            />
            <RangeField
              label={t('parameters:colorMergeThreshold')}
              display={String(colorThreshold)}
              value={colorThreshold}
              min={10}
              max={100}
              onChange={onColorThresholdChange}
            />
          </>
        ) : (
          <>
            <RangeField
              label={t('parameters:numberOfColors')}
              display={String(numColors)}
              value={numColors}
              min={2}
              max={32}
              onChange={onNumColorsChange}
            />
            <RangeField
              label={t('parameters:simplificationEpsilon')}
              display={(epsilon ?? 0).toFixed(1)}
              value={epsilon}
              min={0.5}
              max={10}
              step={0.5}
              onChange={onEpsilonChange}
            />
            <RangeField
              label={t('parameters:minArea')}
              display={`${minArea.toFixed(1)} mm²`}
              value={minArea}
              min={0.1}
              max={20}
              step={0.1}
              onChange={onMinAreaChange}
            />
          </>
        )}
      </RailSection>

      <RailSection index={3} title={t('converter:sectionLayers')}>
        <RangeField
          label={t('parameters:colorLayers')}
          display={String(layerCount)}
          value={layerCount}
          min={4}
          max={maxLayerCount}
          step={1}
          onChange={onLayerCountChange}
          hint={t('parameters:layerLimit', { max: maxLayerCount })}
        />
        <RangeField
          label={t('parameters:layerHeight')}
          display={`${layerHeight.toFixed(2)} mm`}
          value={layerHeight}
          min={LAYER_HEIGHT_MIN_MM}
          max={LAYER_HEIGHT_MAX_MM}
          step={0.01}
          onChange={onLayerHeightChange}
        />
        <div role="group" aria-labelledby={detailSizeLabelId}>
          <div className="flex items-baseline justify-between gap-3">
            <span id={detailSizeLabelId} className="text-sm font-medium text-ink-soft">{t('parameters:detailSizeNozzleLineWidth')}</span>
            <span className="tv-value shrink-0">{(detailSize ?? 0).toFixed(2)} mm</span>
          </div>
          <div className="tv-seg mt-2">
            {DETAIL_SIZES_MM.map((val) => (
              <button
                key={val}
                type="button"
                aria-pressed={Math.abs((detailSize ?? 0) - val) < 0.005}
                onClick={() => onDetailSizeChange(val)}
                className="tv-seg-item group !px-1"
              >
                <span className="block font-mono text-[0.8125rem]">{val.toFixed(2)}</span>
                <span className="block text-[10px] font-medium leading-tight opacity-70">
                  {t('parameters:nozzle', { diameter: (val - 0.02).toFixed(1) })}
                </span>
              </button>
            ))}
          </div>
        </div>
        <RangeField
          label={t('parameters:pixelSize')}
          display={`${(pixelSize ?? 0).toFixed(2)} mm`}
          value={pixelSize}
          min={0.01}
          max={5}
          step="any"
          onChange={onPixelSizeChange}
        />
        {targetWidth > 0 && (
          <div>
            <label className="text-sm font-medium text-ink-soft" htmlFor="maxDimension">{t('parameters:maxDimensionWidthOrHeight')}</label>
            <div className="mt-1.5 flex items-center gap-3">
              <div className="relative w-32 shrink-0">
                <input
                  id="maxDimension"
                  type="number"
                  min="1"
                  max="500"
                  step="1"
                  value={maxDimensionInput}
                  onChange={(e) => {
                    setIsEditingMaxDimension(true);
                    setMaxDimensionInput(e.target.value);
                  }}
                  onFocus={() => setIsEditingMaxDimension(true)}
                  onBlur={commitMaxDimension}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.currentTarget.blur();
                    }
                    if (e.key === 'Escape') {
                      setIsEditingMaxDimension(false);
                      setMaxDimensionInput(formatMaxDimension(maxDimension));
                      e.currentTarget.blur();
                    }
                  }}
                  className="tv-input pr-10 font-mono"
                />
                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-ink-muted">mm</span>
              </div>
              <p className="tv-value text-ink-muted">
                {t('parameters:currentSize', { width: targetWidth.toFixed(1), height: targetHeight.toFixed(1) })}
              </p>
            </div>
          </div>
        )}
      </RailSection>

      <RailSection index={4} title={t('converter:sectionBacking')}>
        <div>
          <label className="text-sm font-medium text-ink-soft" htmlFor="whiteBackingLayers">{t('parameters:whiteBackingLayers')}</label>
          <div className="mt-1.5 flex items-center gap-3">
            <input
              id="whiteBackingLayers"
              type="number"
              min="0"
              max="5"
              step="1"
              value={whiteBackingLayers}
              onChange={(e) => onWhiteBackingLayersChange(Math.max(0, Math.min(5, parseInt(e.target.value || '0', 10))))}
              className="tv-input w-20 font-mono"
            />
          </div>
        </div>

        <div>
          <p id={backingFilamentLabelId} className="text-sm font-medium text-ink-soft">{t('parameters:backingFilament')}</p>
          <div role="group" aria-labelledby={backingFilamentLabelId} className="mt-1.5 flex flex-wrap gap-1.5">
            {filamentColors.map((filament) => {
              const label = filamentLabel(filament);
              return (
                <button
                  key={label}
                  type="button"
                  aria-pressed={backingFilament === label}
                  disabled={whiteBackingLayers === 0}
                  onClick={() => onBackingFilamentChange(label)}
                  className="inline-flex items-center gap-1.5 rounded-sheet border border-rule-strong bg-paper-raised px-2 py-1 text-xs font-semibold text-ink-soft transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-45 aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-paper-raised"
                >
                  <span aria-hidden="true" className="h-3 w-3 rounded-[2px] border border-ink/25" style={{ background: filament.hex }} />
                  {filament.name}
                </button>
              );
            })}
          </div>
          <p className="tv-help mt-1">{t('parameters:backingFilamentHelp')}</p>
        </div>

        <div className="flex items-center gap-4 rounded-sheet border border-rule bg-paper-raised p-3">
          <StackDiagram
            stack={printStack}
            backingHex={filamentColors.find((filament) => filamentLabel(filament) === printStack.backingFilament)?.hex}
          />
          <div className="min-w-0 space-y-1">
            <p className="text-xs text-ink-soft">
              {t('parameters:stack', { optical: printStack.opticalLayerCount, backing: printStack.whiteBackingLayers, total: printStack.totalLayerCount })}
            </p>
            <p className="text-xs text-ink-muted">
              {t('parameters:actualExportHeight')}{' '}
              <span className="tv-value">{printStack.totalHeightMm.toFixed(2)} mm</span>
            </p>
          </div>
        </div>
      </RailSection>

      {hasImage && (
        <div className="sticky bottom-0 z-10 -mx-1 flex gap-2 border-t border-rule bg-paper/95 px-1 py-3 backdrop-blur-sm md:col-span-2 xl:col-span-1">
          <button
            type="button"
            onClick={onReprocess}
            disabled={processing}
            className="tv-btn-primary flex-1 whitespace-nowrap !px-3"
          >
            <RefreshCw className={`h-4 w-4 ${processing ? 'animate-spin' : ''}`} aria-hidden="true" />
            {processing ? t('common:processing') : t('parameters:reprocess')}
          </button>
          {onAutoOptimize && (
            <button
              type="button"
              onClick={onAutoOptimize}
              disabled={processing}
              className="tv-btn-outline flex-1 whitespace-nowrap !px-3"
            >
              <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
              {t('parameters:autoOptimizeParameters')}
            </button>
          )}
        </div>
      )}
    </>
  );
};
