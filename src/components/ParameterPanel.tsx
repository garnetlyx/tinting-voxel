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
          Pixel Size: {pixelSize} mm
        </label>
        <input
          type="range"
          min="0.08"
          max="1"
          step="0.01"
          value={pixelSize}
          onChange={(e) => onPixelSizeChange(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>

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
