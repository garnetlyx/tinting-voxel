/**
 * Mode selector component for switching between Pixel and SVG processing modes
 */
import React from 'react';
import type { ProcessingMode } from '../api/types';

interface ModeSelectorProps {
  mode: ProcessingMode;
  onModeChange: (mode: ProcessingMode) => void;
  disabled?: boolean;
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({
  mode,
  onModeChange,
  disabled = false,
}) => {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Processing Mode
      </label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onModeChange('pixel')}
          disabled={disabled}
          className={`flex-1 py-2 px-4 rounded-lg border-2 transition-colors ${
            mode === 'pixel'
              ? 'border-purple-600 bg-purple-50 text-purple-700'
              : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <div className="font-medium">Pixel</div>
          <div className="text-xs mt-1 opacity-75">
            Best for pixel art, fine details
          </div>
        </button>
        <button
          type="button"
          onClick={() => onModeChange('svg')}
          disabled={disabled}
          className={`flex-1 py-2 px-4 rounded-lg border-2 transition-colors ${
            mode === 'svg'
              ? 'border-purple-600 bg-purple-50 text-purple-700'
              : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <div className="font-medium">SVG</div>
          <div className="text-xs mt-1 opacity-75">
            Best for logos, simple shapes
          </div>
        </button>
      </div>
    </div>
  );
};
