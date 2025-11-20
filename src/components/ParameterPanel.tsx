/**
 * Parameter adjustment panel component
 */
import React from 'react';

interface ParameterPanelProps {
  maxColors: number;
  colorThreshold: number;
  layerHeight: number;
  pixelSize: number;
  onMaxColorsChange: (value: number) => void;
  onColorThresholdChange: (value: number) => void;
  onLayerHeightChange: (value: number) => void;
  onPixelSizeChange: (value: number) => void;
  onReprocess: () => void;
  processing: boolean;
  hasImage: boolean;
}

export const ParameterPanel: React.FC<ParameterPanelProps> = ({
  maxColors,
  colorThreshold,
  layerHeight,
  pixelSize,
  onMaxColorsChange,
  onColorThresholdChange,
  onLayerHeightChange,
  onPixelSizeChange,
  onReprocess,
  processing,
  hasImage,
}) => {
  return (
    <div className="mb-6 p-4 bg-gray-50 rounded-lg space-y-4">
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
