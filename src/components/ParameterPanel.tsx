import { useTranslation } from '../i18n';
/**
 * Parameter adjustment panel component with mode-specific parameters
 */
import React, { useEffect, useState } from 'react';
import type { PrintStackInfo, ProcessingMode } from '../api/types';
import { ModeSelector } from './ModeSelector';

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
  // Base plate
  basePlateThickness: number;
  onBasePlateThicknessChange: (value: number) => void;
  // Double-sided
  doubleSided: boolean;
  onDoubleSidedChange: (value: boolean) => void;
  printStack: PrintStackInfo;
  onReprocess: () => void;
  processing: boolean;
  hasImage: boolean;
  onAutoOptimize?: () => void;
}

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
  basePlateThickness,
  onBasePlateThicknessChange,
  doubleSided,
  onDoubleSidedChange,
  printStack,
  onReprocess,
  processing,
  hasImage,
  onAutoOptimize,
}) => {
  const { t } = useTranslation();
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
    <div className="mb-6 p-4 bg-gray-50 rounded-lg space-y-4">
      <ModeSelector
        mode={mode}
        onModeChange={onModeChange}
        disabled={processing}
      />

      {mode === 'pixel' ? (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:maxColors')}{' '}{maxColors}
            </label>
            <input
              type="range"
              min="2"
              max="100"
              value={maxColors}
              onChange={(e) => onMaxColorsChange(parseInt(e.target.value))}
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:colorMergeThreshold')}{' '}{colorThreshold}
            </label>
            <input
              type="range"
              min="10"
              max="100"
              value={colorThreshold}
              onChange={(e) => onColorThresholdChange(parseInt(e.target.value))}
              className="w-full"
            />
          </div>
        </>
      ) : (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:numberOfColors')}{' '}{numColors}
            </label>
            <input
              type="range"
              min="2"
              max="32"
              value={numColors}
              onChange={(e) => onNumColorsChange(parseInt(e.target.value))}
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:simplificationEpsilon')}{(epsilon ?? 0).toFixed(1)}
            </label>
            <input
              type="range"
              min="0.5"
              max="10"
              step="0.5"
              value={epsilon}
              onChange={(e) => onEpsilonChange(parseFloat(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">{t('parameters:simplificationHelp')}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:minArea')}{' '}{minArea.toFixed(1)} mm²
            </label>
            <input
              type="range"
              min="0.1"
              max="20"
              step="0.1"
              value={minArea}
              onChange={(e) => onMinAreaChange(parseFloat(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">{t('parameters:minimumAreaHelp')}</p>
          </div>
        </>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:colorLayers')}{' '}{layerCount} <span className="text-xs font-normal text-gray-500">{t('parameters:layerLimit', { max: maxLayerCount })}</span>
        </label>
        <input
          type="range"
          min="4"
          max={maxLayerCount}
          step="1"
          value={layerCount}
          onChange={(e) => onLayerCountChange(parseInt(e.target.value, 10))}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">{t('parameters:layerCountHelp')}</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:layerHeight')}{' '}{layerHeight.toFixed(2)} mm
        </label>
        <input
          type="range"
          min="0.04"
          max={layerHeight > 0.28 ? Math.max(1.00, layerHeight) : 0.28}
          step="0.01"
          value={layerHeight}
          onChange={(e) => onLayerHeightChange(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:detailSizeNozzleLineWidth')}{(detailSize ?? 0).toFixed(2)} mm
        </label>
        <div className="flex gap-2">
          {[0.22, 0.42, 0.62, 0.82].map((val) => (
            <button
              key={val}
              onClick={() => onDetailSizeChange(val)}
              className={`flex-1 py-1.5 text-xs rounded border transition-colors ${
                Math.abs((detailSize ?? 0) - val) < 0.005
                  ? 'bg-purple-600 text-white border-purple-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-purple-400'
              }`}
            >
              {val.toFixed(2)}
              <span className="block text-gray-400 text-[10px] leading-tight" style={{color: Math.abs((detailSize ?? 0) - val) < 0.005 ? 'rgba(255,255,255,0.75)' : undefined}}>
                {t('parameters:nozzle', { diameter: (val - 0.02).toFixed(1) })}
              </span>
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-1">{t('parameters:detailSizeHelp')}</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:pixelSize')}{(pixelSize ?? 0).toFixed(2)} mm
        </label>
        <input
          type="range"
          min="0.2"
          max="2"
          step="0.01"
          value={pixelSize}
          onChange={(e) => onPixelSizeChange(parseFloat(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">{t('parameters:pixelSizeHelp')}</p>
      </div>

      {targetWidth > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2" htmlFor="maxDimension">{t('parameters:maxDimensionWidthOrHeight')}</label>
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
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-500">
            {t('parameters:currentSize', { width: targetWidth.toFixed(1), height: targetHeight.toFixed(1) })}
          </p>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2" htmlFor="whiteBackingLayers">{t('parameters:whiteBackingLayers')}</label>
        <input
          id="whiteBackingLayers"
          type="number"
          min="0"
          max="5"
          step="1"
          value={whiteBackingLayers}
          onChange={(e) => onWhiteBackingLayersChange(Math.max(0, Math.min(5, parseInt(e.target.value || '0', 10))))}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">
          {t('parameters:stack', { optical: printStack.opticalLayerCount, backing: printStack.whiteBackingLayers, total: printStack.totalLayerCount })}
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">{t('parameters:basePlateThickness')}{' '}{basePlateThickness} mm
        </label>
        <input
          type="range"
          min="0"
          max="2"
          step="0.1"
          value={basePlateThickness}
          onChange={(e) => onBasePlateThicknessChange(parseFloat(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">
          {basePlateThickness === 0 ? t('parameters:noBasePlate') : t('parameters:basePlateHelp')}
        </p>
      </div>

      <div className="rounded-md border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600">{t('parameters:actualExportHeight')}{' '}{printStack.totalHeightMm.toFixed(2)} mm
      </div>

      {mode === 'pixel' && (
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="doubleSided"
            checked={doubleSided}
            onChange={(e) => onDoubleSidedChange(e.target.checked)}
            className="h-4 w-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
          />
          <label htmlFor="doubleSided" className="text-sm font-medium text-gray-700">{t('parameters:doubleSidedPrint')}</label>
          <p className="text-xs text-gray-500">{t('parameters:doubleSidedHelp')}</p>
        </div>
      )}

      {hasImage && (
        <button
          onClick={onReprocess}
          disabled={processing}
          className="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:bg-gray-400"
        >
          {processing ? t('common:processing') : t('parameters:reprocess')}
        </button>
      )}

      {hasImage && onAutoOptimize && (
        <button
          onClick={onAutoOptimize}
          disabled={processing}
          className="w-full py-2 border border-purple-500 text-purple-600 rounded-lg hover:bg-purple-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >{t('parameters:autoOptimizeParameters')}</button>
      )}
    </div>
  );
};
