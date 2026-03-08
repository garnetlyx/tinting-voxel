/**
 * Parameter adjustment panel component with mode-specific parameters
 */
import React from 'react';
import type { ProcessingMode } from '../api/types';
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
  pixelSize: number;
  onLayerHeightChange: (value: number) => void;
  onPixelSizeChange: (value: number) => void;
  // Detail size
  detailSize: number;
  onDetailSizeChange: (value: number) => void;
  // Target physical size
  targetWidth: number;
  targetHeight: number;
  onTargetWidthChange: (value: number) => void;
  // Base plate
  basePlateThickness: number;
  onBasePlateThicknessChange: (value: number) => void;
  // Double-sided
  doubleSided: boolean;
  onDoubleSidedChange: (value: boolean) => void;
  onReprocess: () => void;
  processing: boolean;
  hasImage: boolean;
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
  pixelSize,
  onLayerHeightChange,
  onPixelSizeChange,
  detailSize,
  onDetailSizeChange,
  targetWidth,
  targetHeight,
  onTargetWidthChange,
  basePlateThickness,
  onBasePlateThicknessChange,
  doubleSided,
  onDoubleSidedChange,
  onReprocess,
  processing,
  hasImage,
}) => {
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
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Colors: {maxColors}
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
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Color Merge Threshold: {colorThreshold}
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
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Number of Colors: {numColors}
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
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Simplification (Epsilon): {epsilon.toFixed(1)}
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
            <p className="text-xs text-gray-500 mt-1">
              Higher values produce simpler shapes with fewer vertices
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Min Area: {minArea} px
            </label>
            <input
              type="range"
              min="10"
              max="500"
              step="10"
              value={minArea}
              onChange={(e) => onMinAreaChange(parseInt(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">
              Filters out small contours below this area
            </p>
          </div>
        </>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Layer Height: {layerHeight} mm
        </label>
        <input
          type="range"
          min="0.04"
          max="0.28"
          step="0.01"
          value={layerHeight}
          onChange={(e) => onLayerHeightChange(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Detail Size (Min Pixel): {detailSize.toFixed(2)} mm
        </label>
        <input
          type="range"
          min="0.2"
          max="0.8"
          step="0.05"
          value={detailSize}
          onChange={(e) => onDetailSizeChange(parseFloat(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">
          Minimum physical size of a single pixel. Prevents too-small details.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Pixel Size: {pixelSize.toFixed(2)} mm
        </label>
        <input
          type="range"
          min={detailSize}
          max="2"
          step="0.01"
          value={pixelSize}
          onChange={(e) => onPixelSizeChange(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>

      {targetWidth > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Target Width: {targetWidth} mm (Height: {targetHeight} mm)
          </label>
          <input
            type="number"
            min="1"
            max="500"
            step="0.1"
            value={targetWidth}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val) && val > 0) onTargetWidthChange(val);
            }}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-purple-500 focus:border-purple-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            Enter desired physical width in mm. Height scales proportionally.
          </p>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Base Plate Thickness: {basePlateThickness} mm
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
          {basePlateThickness === 0 ? 'No base plate' : `Adds a solid base plate below color layers`}
        </p>
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
          <label htmlFor="doubleSided" className="text-sm font-medium text-gray-700">
            Double-sided print
          </label>
          <p className="text-xs text-gray-500">
            Generates mirrored back side for two-sided viewing
          </p>
        </div>
      )}

      {hasImage && (
        <button
          onClick={onReprocess}
          disabled={processing}
          className="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:bg-gray-400"
        >
          {processing ? 'Processing...' : 'Reprocess'}
        </button>
      )}
    </div>
  );
};
