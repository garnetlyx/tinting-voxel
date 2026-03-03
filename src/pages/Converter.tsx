/**
 * Main converter page component
 */
import React, { useState } from 'react';
import { Settings, Palette, Image as ImageIcon, Layers } from 'lucide-react';
import { useImageProcessor } from '../hooks/useImageProcessor';
import {
  ErrorMessage,
  LoadingSpinner,
  ImageUploader,
  ImageEditor,
  ParameterPanel,
  FilamentConfigPanel,
  FilamentPreview,
  FilamentPresetManager,
  ImageComparison,
  ColorAdjustmentPanel,
  VectorColorList,
  DownloadButtons,
  ThreeDPreview,
  BatchProcessor,
  PaletteLibrary,
} from '../components';

type AppMode = 'single' | 'batch';

const Converter: React.FC = () => {
  const [showSettings, setShowSettings] = useState(true);
  const [appMode, setAppMode] = useState<AppMode>('single');

  const {
    image,
    rawImage,
    isEditing,
    processing,
    processingStage,
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
    layerCount,
    basePlateThickness,
    doubleSided,
    targetWidth,
    targetHeight,
    imageDimensions,

    // Filament state
    filamentPreset,
    filamentColors,
    isFilamentConfigValid,

    // Filament storage
    filamentStorage,

    // Actions
    setMode,
    setMaxColors,
    setColorThreshold,
    setEpsilon,
    setMinArea,
    setNumColors,
    setLayerHeight,
    setPixelSize,
    setTargetWidth,
    setBasePlateThickness,
    setDoubleSided,
    loadPreset,
    loadSavedPresetColors,
    updateFilamentColor,
    addFilamentColor,
    removeFilamentColor,
    handleFile,
    handleImageUpload,
    handleApplyEdit,
    handleCancelEdit,
    handleReprocess,
    handleDownloadCSV,
    handleDownloadSTL,
    handleDownload3MF,
    handleDownloadPrintSettings,
    updateColorBlock,
    mergeColorBlocks,
    deleteColorBlock,
  } = useImageProcessor();

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-8">
      <div className="max-w-7xl 2xl:max-w-[1600px] mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-6 sm:p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
              <Palette className="w-8 h-8 text-purple-600" />
              Image to STL Color Block Converter
            </h1>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title={showSettings ? "Hide Settings Sidebar" : "Show Settings Sidebar"}
            >
              <Settings className={`w-6 h-6 ${showSettings ? "text-purple-600" : "text-gray-600"}`} />
            </button>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
            {/* Left Sidebar: Parameter Panel */}
            {showSettings && (
              <div className="xl:col-span-4 space-y-6">
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
                  targetWidth={targetWidth}
                  targetHeight={targetHeight}
                  onTargetWidthChange={setTargetWidth}
                  basePlateThickness={basePlateThickness}
                  onBasePlateThicknessChange={setBasePlateThickness}
                  doubleSided={doubleSided}
                  onDoubleSidedChange={setDoubleSided}
                  onReprocess={handleReprocess}
                  processing={processing}
                  hasImage={image !== null}
                />
                <div className="p-4 bg-gray-50 rounded-lg space-y-4">
                  <FilamentConfigPanel
                    filamentPreset={filamentPreset}
                    filamentColors={filamentColors}
                    isValid={isFilamentConfigValid}
                    onLoadPreset={loadPreset}
                    onUpdateColor={updateFilamentColor}
                    onAddColor={addFilamentColor}
                    onRemoveColor={removeFilamentColor}
                    disabled={processing}
                  />
                  <FilamentPreview
                    filamentColors={filamentColors}
                    filamentPreset={filamentPreset}
                    layerCount={layerCount}
                    layerHeight={layerHeight}
                    isConfigValid={isFilamentConfigValid}
                    disabled={processing}
                  />
                  <FilamentPresetManager
                    presets={filamentStorage.presets}
                    currentColors={filamentColors}
                    isConfigValid={isFilamentConfigValid}
                    onLoadPreset={loadSavedPresetColors}
                    onSavePreset={filamentStorage.savePreset}
                    onUpdatePreset={filamentStorage.updatePreset}
                    onDeletePreset={filamentStorage.deletePreset}
                    onRenamePreset={filamentStorage.renamePreset}
                    onExportPresets={filamentStorage.exportPresets}
                    onImportPresets={filamentStorage.importPresets}
                    disabled={processing}
                  />
                  <PaletteLibrary
                    onApplyPalette={loadSavedPresetColors}
                    disabled={processing}
                  />
                </div>
              </div>
            )}

            {/* Right Main Content */}
            <div className={showSettings ? "xl:col-span-8 space-y-6" : "xl:col-span-12 space-y-6"}>
              {/* Mode Tabs */}
              <div className="flex border-b border-gray-200">
                <button
                  onClick={() => setAppMode('single')}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${appMode === 'single'
                      ? 'border-purple-600 text-purple-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                >
                  <ImageIcon className="w-4 h-4" />
                  Single Image
                </button>
                <button
                  onClick={() => setAppMode('batch')}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${appMode === 'batch'
                      ? 'border-purple-600 text-purple-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                >
                  <Layers className="w-4 h-4" />
                  Batch Processing
                </button>
              </div>

              {/* Single Image Mode */}
              {appMode === 'single' && (
                <div className="space-y-6">
                  {/* Image Uploader */}
                  <ImageUploader onImageUpload={handleImageUpload} onFileDrop={handleFile} />

                  {/* Image Editor (crop/resize) */}
                  {isEditing && rawImage && (
                    <ImageEditor
                      image={rawImage}
                      onApply={handleApplyEdit}
                      onCancel={handleCancelEdit}
                      disabled={processing}
                    />
                  )}

                  {/* Error Message */}
                  {error && <ErrorMessage message={error} />}

                  {/* Loading Spinner with progress stages */}
                  {processing && <LoadingSpinner stage={processingStage} />}

                  {/* Results */}
                  {!processing && !isEditing && hasResults && (
                    <div className="space-y-6">
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
                        onDownload3MF={handleDownload3MF}
                        onDownloadPrintSettings={handleDownloadPrintSettings}
                        processing={processing}
                        showCSV={mode === 'pixel'}
                      />

                      {/* 3D Preview (pixel mode only) */}
                      {mode === 'pixel' && colorBlocks.length > 0 && (
                        <ThreeDPreview
                          colorBlocks={colorBlocks}
                          imageDimensions={imageDimensions}
                          layerHeight={layerHeight}
                          pixelSize={pixelSize}
                          layerCount={layerCount}
                          basePlateThickness={basePlateThickness}
                          doubleSided={doubleSided}
                        />
                      )}

                      {/* Color Blocks Grid with manual adjustment (pixel mode only) */}
                      {mode === 'pixel' && (
                        <ColorAdjustmentPanel
                          colorBlocks={colorBlocks}
                          onUpdateColor={updateColorBlock}
                          onMergeColors={mergeColorBlocks}
                          onDeleteColor={deleteColorBlock}
                        />
                      )}

                      {/* Vector Color List (svg mode) */}
                      {mode === 'svg' && <VectorColorList vectorResults={vectorResults} />}
                    </div>
                  )}

                  {/* Original Image Preview (when no results yet) */}
                  {image && !hasResults && !processing && !isEditing && (
                    <div>
                      <h3 className="text-lg font-semibold text-gray-800 mb-3">Original Image Preview</h3>
                      <img
                        src={image.src}
                        alt="Preview"
                        className="max-w-full rounded-lg shadow-md"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Batch Processing Mode */}
              {appMode === 'batch' && (
                <BatchProcessor
                  maxColors={maxColors}
                  colorThreshold={colorThreshold}
                  pixelSize={pixelSize}
                  layerHeight={layerHeight}
                  layerCount={layerCount}
                  basePlateThickness={basePlateThickness}
                  doubleSided={doubleSided}
                  filamentPreset={filamentPreset ?? undefined}
                  filamentColors={filamentPreset ? undefined : filamentColors}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Converter;
