import { LanguageSelector } from '../components/LanguageSelector';
import { useTranslation } from '../i18n';
/**
 * Main converter page component
 */
import React, { useEffect, useRef, useState } from 'react';
import { Settings, Image as ImageIcon, Layers, Loader2 } from 'lucide-react';
import { useImageProcessor } from '../hooks/useImageProcessor';
import { useParamSearch } from '../hooks/useParamSearch';
import { useBackendReady } from '../hooks/useBackendReady';
import {
  BugReportButton,
  ErrorMessage,
  LoadingSpinner,
  ImageUploader,
  ImageEditor,
  ParameterPanel,
  FilamentConfigPanel,
  FilamentPreview,
  FilamentPresetManager,
  ImageComparison,
  MappedBlendPalette,
  ColorAdjustmentPanel,
  VectorColorList,
  DownloadButtons,
  ThreeDPreview,
  BatchProcessor,
  PaletteLibrary,
  ParamSearchModal,
} from '../components';

type AppMode = 'single' | 'batch';

const Converter: React.FC = () => {
  const { t } = useTranslation();
  const [showSettings, setShowSettings] = useState(true);
  const [appMode, setAppMode] = useState<AppMode>('single');

  const {
    image,
    currentImageFile,
    rawImage,
    isEditing,
    processing,
    processingStage,
    error,
    mode,
    colorBlocks,
    vectorResults,
    processedImageUrl,
    segmentationImageUrl,
    mappedBlockColors,
    mappedBlendPalette,
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
    detailSize,
    layerCount,
    maxLayerCount,
    whiteBackingLayers,
    backingMode,
    setBackingMode,
    targetWidth,
    targetHeight,
    maxDimension,
    imageDimensions,
    printStack,

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
    allTransparent,
    setLayerCount,
    setPixelSize,
    setDetailSize,
    setWhiteBackingLayers,
    setMaxDimension,
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

  const backendReady = useBackendReady();
  const paramSearch = useParamSearch();
  const [paramSearchOpen, setParamSearchOpen] = useState(false);
  const [showParamSearchPrompt, setShowParamSearchPrompt] = useState(false);
  // Track whether the current processing run was triggered by a fresh image upload
  const pendingParamSearchPromptRef = useRef(false);

  // Show the prompt once processing completes after a fresh upload
  useEffect(() => {
    if (!processing && hasResults && pendingParamSearchPromptRef.current) {
      pendingParamSearchPromptRef.current = false;
      setShowParamSearchPrompt(true);
    }
  }, [processing, hasResults]);
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-8">
      <div className="max-w-7xl 2xl:max-w-[1600px] mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-6 sm:p-8">
          {/* Header */}
          <div className="flex flex-col gap-3 mb-8 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="text-xl sm:text-3xl font-bold text-gray-800 flex items-center gap-3 min-w-0 flex-1">
              <img src="/brand.svg" alt="" width={32} height={32} className="w-6 h-6 sm:w-8 sm:h-8 shrink-0" />{t('converter:title')}</h1>
            <div className="flex shrink-0 items-center justify-end gap-2">
            <LanguageSelector />
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title={showSettings ? t('converter:hideSettingsSidebar') : t('converter:showSettingsSidebar')}
            >
              <Settings className={`w-6 h-6 ${showSettings ? "text-purple-600" : "text-gray-600"}`} />
            </button>
            </div>
          </div>

          {/* Backend warming-up banner */}
          {!backendReady && (
            <div className="mb-6 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
              <Loader2 className="w-5 h-5 animate-spin shrink-0" />
              <span className="text-sm font-medium">{t('converter:serverStarting')}</span>
            </div>
          )}

          <div className={`grid grid-cols-1 xl:grid-cols-12 gap-8 ${!backendReady ? 'pointer-events-none opacity-50' : ''}`}>
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
                  layerCount={layerCount}
                  maxLayerCount={maxLayerCount}
                  pixelSize={pixelSize}
                  onLayerHeightChange={setLayerHeight}
                  allTransparent={allTransparent}
                  onLayerCountChange={setLayerCount}
                  onPixelSizeChange={setPixelSize}
                  detailSize={detailSize}
                  onDetailSizeChange={setDetailSize}
                  targetWidth={targetWidth}
                  targetHeight={targetHeight}
                  maxDimension={maxDimension}
                  onMaxDimensionChange={setMaxDimension}
                  whiteBackingLayers={whiteBackingLayers}
                  onWhiteBackingLayersChange={setWhiteBackingLayers}
                  backingMode={backingMode}
                  onBackingModeChange={setBackingMode}
                  printStack={printStack}
                  onReprocess={() => handleReprocess()}
                  processing={processing}
                  hasImage={image !== null}
                  onAutoOptimize={() => {
                    setShowParamSearchPrompt(false);
                    paramSearch.openConfig();
                    setParamSearchOpen(true);
                  }}
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
                  <ImageIcon className="w-4 h-4" />{t('converter:singleImage')}</button>
                <button
                  onClick={() => setAppMode('batch')}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${appMode === 'batch'
                    ? 'border-purple-600 text-purple-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                >
                  <Layers className="w-4 h-4" />{t('converter:batchProcessing')}</button>
              </div>

              {/* Single Image Mode */}
              {appMode === 'single' && (
                <div className="space-y-6">
                  {/* Image Uploader */}
                  <ImageUploader
                    onImageUpload={handleImageUpload}
                    onFileDrop={handleFile}
                  />

                  {/* Image Editor (crop/resize) */}
                  {isEditing && rawImage && (
                    <ImageEditor
                      image={rawImage}
                      onApply={(editedImg) => {
                        setShowParamSearchPrompt(false);
                        pendingParamSearchPromptRef.current = true;
                        handleApplyEdit(editedImg);
                      }}
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

                      {/* Param search prompt */}
                      {showParamSearchPrompt && (
                        <div className="flex items-center justify-between gap-4 rounded-lg border border-purple-200 bg-purple-50 px-4 py-3">
                          <p className="text-sm text-purple-800">{t('converter:optimizationPrompt')}</p>
                          <div className="flex gap-2 shrink-0">
                            <button
                              onClick={() => {
                                setShowParamSearchPrompt(false);
                                paramSearch.openConfig();
                                setParamSearchOpen(true);
                              }}
                              className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                            >{t('converter:optimize')}</button>
                            <button
                              onClick={() => setShowParamSearchPrompt(false)}
                              className="px-3 py-1.5 text-sm border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
                            >{t('converter:skip')}</button>
                          </div>
                        </div>
                      )}
                      {/* Before/After Comparison */}
                      <ImageComparison
                        originalImage={image}
                        intermediateImageUrl={segmentationImageUrl}
                        intermediateLabel={mode === 'pixel' ? t('converter:groupedColors') : t('converter:vectorizedRegions')}
                        processedImageUrl={processedImageUrl}
                        colorCount={resultCount}
                        processedLabel={t('converter:simulatedPrint')}
                      />

                      {mappedBlendPalette.length > 0 && (
                        <MappedBlendPalette entries={mappedBlendPalette} />
                      )}

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
                          mappedBlockColors={mappedBlockColors}
                          imageDimensions={imageDimensions}
                          layerHeight={layerHeight}
                          pixelSize={pixelSize}
                          layerCount={layerCount}
                          whiteBackingLayers={whiteBackingLayers}
                          printStack={printStack}
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
                      <h3 className="text-lg font-semibold text-gray-800 mb-3">{t('converter:originalImagePreview')}</h3>
                      <img
                        src={image.src}
                        alt={t('converter:preview')}
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
                  whiteBackingLayers={whiteBackingLayers}
                  filamentPreset={filamentPreset ?? undefined}
                  filamentColors={filamentPreset ? undefined : filamentColors}
                  detailSize={detailSize}
                />
              )}
            </div>
          </div>
        </div>
      </div>

      <BugReportButton context={{
        appMode, mode, pixelSize, layerHeight, layerCount, whiteBackingLayers,
        imageWidth: imageDimensions.width,
        imageHeight: imageDimensions.height, colorCount: resultCount,
        filamentPreset, processing, error,
      }} />

      {/* Param Search Modal */}
      <ParamSearchModal
        isOpen={paramSearchOpen}
        onClose={() => {
          setParamSearchOpen(false);
          paramSearch.reset();
        }}
        phase={paramSearch.phase === 'idle' ? 'config' : paramSearch.phase}
        progress={paramSearch.progress}
        results={paramSearch.results}
        error={paramSearch.error}
        defaultTargetSizeMm={maxDimension}
        onStart={(targetLongestEdgeMm) => {
          if (!image || !currentImageFile) return;
          paramSearch.startSearch(
            currentImageFile,
            {
              targetLongestEdgeMm,
              // Search the exact image and print configuration currently shown.
              preset: filamentPreset ?? undefined,
              filamentColors: filamentPreset ? undefined : filamentColors,
              mode,
              layerCount,
              layerHeight,
              whiteBackingLayers,
              backingMode,
              maxColors,
              colorThreshold,
              detailSize,
              numColors,
              epsilon,
              minArea,
              strategy: 'random',
              nTrials: 20,
            },
            imageDimensions,
          );
        }}
        onApplyParams={(params, resultMode, targetLongestEdgeMm) => {
          // Apply returned params to the relevant state setters AND pass them as
          // overrides to the reprocess call: setState is async, so a reprocess
          // fired in the same tick would otherwise read the previous values.
          const overrides: Parameters<typeof handleReprocess>[1] = {};
          if ('max_colors' in params) { setMaxColors(params.max_colors); overrides.maxColors = params.max_colors; }
          if ('color_threshold' in params) { setColorThreshold(params.color_threshold); overrides.colorThreshold = params.color_threshold; }
          if ('num_colors' in params) { setNumColors(params.num_colors); overrides.numColors = params.num_colors; }
          if ('epsilon' in params) { setEpsilon(params.epsilon); overrides.epsilon = params.epsilon; }
          if ('min_area' in params) { setMinArea(params.min_area); overrides.minArea = params.min_area; }
          if ('detail_size' in params) { setDetailSize(params.detail_size); overrides.detailSize = params.detail_size; }
          if ('white_backing_layers' in params) { setWhiteBackingLayers(params.white_backing_layers); overrides.whiteBackingLayers = params.white_backing_layers; }
          const nextMode = resultMode === 'pixel' || resultMode === 'svg' ? resultMode : undefined;
          if (nextMode) setMode(nextMode);
          // Re-apply the pixel size the search evaluated at, so the reprocessed
          // result matches the card preview (pixel_size is a run-fixed param and
          // is not part of the per-result params dict).
          const longestPx = Math.max(imageDimensions.width, imageDimensions.height);
          const nextPixelSize = longestPx > 0 ? targetLongestEdgeMm / longestPx : undefined;
          if (nextPixelSize) setPixelSize(nextPixelSize);
          handleReprocess(nextPixelSize, overrides, nextMode);
        }}
      />
    </div>
  );
};

export default Converter;
