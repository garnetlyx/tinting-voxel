/**
 * Main converter page component
 */
import React, { useState } from 'react';
import { Settings, Palette } from 'lucide-react';
import { useImageProcessor } from '../hooks/useImageProcessor';
import {
  ErrorMessage,
  LoadingSpinner,
  ImageUploader,
  ParameterPanel,
  ImageComparison,
  ColorBlocksList,
  VectorColorList,
  DownloadButtons,
} from '../components';

const Converter: React.FC = () => {
  const [showSettings, setShowSettings] = useState(true);

  const {
    image,
    processing,
    error,
    mode,
    colorBlocks,
    vectorResults,
    processedImageUrl,
    hasResults,
    resultCount,

    // Pixel mode params
    maxColors,
    colorThreshold,

    // SVG mode params
    epsilon,
    minArea,
    numColors,

    // Shared params
    layerHeight,
    pixelSize,

    // Actions
    setMode,
    setMaxColors,
    setColorThreshold,
    setEpsilon,
    setMinArea,
    setNumColors,
    setLayerHeight,
    setPixelSize,
    handleImageUpload,
    handleReprocess,
    handleDownloadCSV,
    handleDownloadSTL,
  } = useImageProcessor();

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
              <Palette className="w-8 h-8 text-purple-600" />
              Image to STL Color Block Converter
            </h1>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Settings className="w-6 h-6 text-gray-600" />
            </button>
          </div>

          {/* Parameter Panel */}
          {showSettings && (
            <ParameterPanel
              mode={mode}
              onModeChange={setMode}
              maxColors={maxColors}
              colorThreshold={colorThreshold}
              onMaxColorsChange={setMaxColors}
              onColorThresholdChange={setColorThreshold}
              epsilon={epsilon}
              minArea={minArea}
              numColors={numColors}
              onEpsilonChange={setEpsilon}
              onMinAreaChange={setMinArea}
              onNumColorsChange={setNumColors}
              layerHeight={layerHeight}
              pixelSize={pixelSize}
              onLayerHeightChange={setLayerHeight}
              onPixelSizeChange={setPixelSize}
              onReprocess={handleReprocess}
              processing={processing}
              hasImage={image !== null}
            />
          )}

          {/* Image Uploader */}
          <ImageUploader onImageUpload={handleImageUpload} />

          {/* Error Message */}
          {error && <ErrorMessage message={error} />}

          {/* Loading Spinner */}
          {processing && <LoadingSpinner />}

          {/* Results */}
          {!processing && hasResults && (
            <div>
              {/* Before/After Comparison */}
              <ImageComparison
                originalImage={image}
                processedImageUrl={processedImageUrl}
                colorCount={resultCount}
              />

              {/* Download Buttons */}
              <DownloadButtons
                colorCount={resultCount}
                onDownloadCSV={handleDownloadCSV}
                onDownloadSTL={handleDownloadSTL}
                processing={processing}
                showCSV={mode === 'pixel'}
              />

              {/* Color Blocks Grid (pixel mode only) */}
              {mode === 'pixel' && <ColorBlocksList colorBlocks={colorBlocks} />}

              {/* Vector Color List (svg mode) */}
              {mode === 'svg' && <VectorColorList vectorResults={vectorResults} />}
            </div>
          )}

          {/* Original Image Preview (when no results yet) */}
          {image && !hasResults && !processing && (
            <div className="mt-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">Original Image Preview</h3>
              <img
                src={image.src}
                alt="Preview"
                className="max-w-full rounded-lg shadow-md"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Converter;
