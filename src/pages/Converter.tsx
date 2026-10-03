import { LanguageSelector } from '../components/LanguageSelector';
import { useTranslation } from '../i18n';
/**
 * Main converter page component
 */
import React, { useState } from 'react';
import { Settings, Image as ImageIcon, Layers, Loader2 } from 'lucide-react';
import { useImageProcessor } from '../hooks/useImageProcessor';
import { useParamSearch } from '../hooks/useParamSearch';
import { useBackendReady } from '../hooks/useBackendReady';
import {
  BugReportButton,
  InkStrip,
  RailSection,
  ErrorMessage,
  HeavyJobBanner,
  OversizeDialog,
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
    renderReady,

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
    backingFilament,
    setBackingFilament,
    targetWidth,
    targetHeight,
    maxDimension,
    imageDimensions,
    printStack,

    // Filament state
    filamentPresets,
    filamentCatalogLoading,
    maxModelSidePx,
    maxTargetColors,
    filamentCatalogError,
    reloadFilamentCatalog,
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
  const blocked = !backendReady || filamentCatalogLoading || !!filamentCatalogError;
  const emptyStage = !image && !isEditing && !processing && !hasResults;
  return (
    <div className="min-h-screen">
      <header className="border-b border-ink/15 bg-paper/90 backdrop-blur-sm lg:sticky lg:top-0 lg:z-30">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-3 sm:gap-4 sm:px-6 lg:px-8">
          <img src="/brand.svg" alt="" width={40} height={40} className="h-9 w-9 shrink-0 sm:h-10 sm:w-10" />
          <h1 className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-3">
            <span className="tv-display whitespace-nowrap text-[1.5rem] sm:text-[2.15rem]">Tinting Voxel</span>
            <span className="sr-only truncate text-sm text-ink-muted sm:not-sr-only">{t('converter:tagline')}</span>
          </h1>
          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-4">
            <InkStrip colors={filamentColors} className="hidden md:flex" />
            <LanguageSelector />
            <button
              type="button"
              onClick={() => setShowSettings(!showSettings)}
              aria-expanded={showSettings}
              aria-controls="print-settings"
              className="tv-btn-ghost !p-2 aria-expanded:text-ink"
              title={showSettings ? t('converter:hideSettingsSidebar') : t('converter:showSettingsSidebar')}
            >
              <Settings className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-4 pb-24 pt-6 sm:px-6 lg:px-8 lg:pt-8">
        {/* Backend warming-up banner */}
        {!backendReady && (
          <div role="status" className="mb-6 flex items-center gap-3 rounded-sheet border border-signal-warn/30 border-l-4 border-l-signal-warn bg-signal-warn/5 px-4 py-3 text-signal-warn">
            <Loader2 className="h-5 w-5 shrink-0 animate-spin" aria-hidden="true" />
            <span className="text-sm font-medium">{t('converter:serverStarting')}</span>
          </div>
        )}

        {filamentCatalogLoading && backendReady && (
          <div role="status" className="mb-6 flex items-center gap-3 text-sm text-ink-muted">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />{t('filaments:loadingPresets')}
          </div>
        )}
        {filamentCatalogError && (
          <div role="alert" className="mb-6 flex items-center gap-3 rounded-sheet border border-signal-error/30 border-l-4 border-l-signal-error bg-signal-error/5 px-4 py-3 text-sm text-signal-error">
            {t('filaments:loadPresetsFailed')}
            <button type="button" onClick={reloadFilamentCatalog} className="font-semibold underline underline-offset-4">{t('filaments:retry')}</button>
          </div>
        )}

        <div
          inert={blocked}
          className={`grid gap-10 ${showSettings ? 'xl:grid-cols-[360px_minmax(0,1fr)] 2xl:grid-cols-[400px_minmax(0,1fr)]' : ''} ${blocked ? 'pointer-events-none opacity-50' : ''}`}
        >
          {/* Stage: upload, editing and results. First in the DOM so phones reach it first. */}
          <section
            aria-label={t('converter:workspace')}
            className={`tv-sheet tv-marks tv-rise min-w-0 self-start p-4 sm:p-6 lg:p-8 ${showSettings ? 'xl:col-start-2 xl:row-start-1' : ''}`}
          >
            {/* Mode Tabs */}
            <div className="tv-seg mb-6 inline-flex">
              <button
                type="button"
                onClick={() => setAppMode('single')}
                aria-pressed={appMode === 'single'}
                className="tv-seg-item flex !flex-none items-center gap-2 whitespace-nowrap !px-4 !text-sm"
              >
                <ImageIcon className="h-4 w-4" aria-hidden="true" />{t('converter:singleImage')}</button>
              <button
                type="button"
                onClick={() => setAppMode('batch')}
                aria-pressed={appMode === 'batch'}
                className="tv-seg-item flex !flex-none items-center gap-2 whitespace-nowrap !px-4 !text-sm"
              >
                <Layers className="h-4 w-4" aria-hidden="true" />{t('converter:batchProcessing')}</button>
            </div>

            {/* Heavy-job queue and oversize confirmations: shared by both modes */}
            <HeavyJobBanner />
            <OversizeDialog />

            {/* Single Image Mode */}
            {appMode === 'single' && (
              <div className="space-y-8">
                {emptyStage && (
                  <div className="max-w-2xl">
                    <p className="tv-display text-balance text-[2.6rem] text-ink sm:text-[3.4rem]">{t('converter:heroTitle')}</p>
                    <p className="mt-3 text-base leading-relaxed text-ink-soft">{t('converter:description')}</p>
                  </div>
                )}

                {/* Image Uploader */}
                <ImageUploader
                  onImageUpload={handleImageUpload}
                  onFileDrop={handleFile}
                  compact={!emptyStage}
                />

                {/* Image Editor (crop/resize) */}
                {isEditing && rawImage && maxModelSidePx !== undefined && (
                  <ImageEditor
                    image={rawImage}
                    maxSidePx={maxModelSidePx}
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
                  <div className="space-y-12">

                    {/* Before/After Comparison */}
                    <ImageComparison
                      originalImage={image}
                      intermediateImageUrl={segmentationImageUrl}
                      intermediateLabel={mode === 'pixel' ? t('converter:groupedColors') : t('converter:vectorizedRegions')}
                      processedImageUrl={processedImageUrl}
                      colorCount={resultCount}
                      processedLabel={t('converter:simulatedPrint')}
                    />

                    {/* Download Buttons */}
                    <DownloadButtons
                      onDownloadCSV={handleDownloadCSV}
                      onDownloadSTL={handleDownloadSTL}
                      onDownload3MF={handleDownload3MF}
                      onDownloadPrintSettings={handleDownloadPrintSettings}
                      processing={processing || !renderReady}
                      showCSV={mode === 'pixel'}
                      summary={`${targetWidth.toFixed(1)} × ${targetHeight.toFixed(1)} × ${printStack.totalHeightMm.toFixed(2)} mm`}
                    />

                    {/* 3D Preview (pixel mode only) */}
                    {mode === 'pixel' && colorBlocks.length > 0 && (
                      <ThreeDPreview
                        colorBlocks={colorBlocks}
                        mappedBlockColors={mappedBlockColors}
                        filamentColors={filamentColors}
                        imageDimensions={imageDimensions}
                        layerHeight={layerHeight}
                        pixelSize={pixelSize}
                        layerCount={layerCount}
                        whiteBackingLayers={whiteBackingLayers}
                        printStack={printStack}
                      />
                    )}

                    {mappedBlendPalette.length > 0 && (
                      <MappedBlendPalette entries={mappedBlendPalette} />
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
                  <figure>
                    <img
                      src={image.src}
                      alt={t('converter:preview')}
                      className="max-w-full rounded-sheet border border-rule"
                    />
                    <figcaption className="mt-2 text-sm font-medium text-ink-soft">{t('converter:originalImagePreview')}</figcaption>
                  </figure>
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
                backingFilament={backingFilament}
                filamentPreset={filamentPreset ?? undefined}
                filamentColors={filamentPreset ? undefined : filamentColors}
                detailSize={detailSize}
              />
            )}
          </section>

          {/* Settings rail */}
          {showSettings && (
            <aside
              id="print-settings"
              aria-label={t('converter:settings')}
              className="tv-scroll grid min-w-0 content-start gap-9 md:grid-cols-2 md:gap-x-12 xl:sticky xl:top-[5.25rem] xl:col-start-1 xl:row-start-1 xl:max-h-[calc(100dvh-6.5rem)] xl:grid-cols-1 xl:self-start xl:overflow-y-auto xl:pr-4"
            >
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
                maxTargetColors={maxTargetColors}
                pixelSize={pixelSize}
                onLayerHeightChange={setLayerHeight}
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
                filamentColors={filamentColors}
                backingFilament={backingFilament}
                onBackingFilamentChange={setBackingFilament}
                printStack={printStack}
                onReprocess={() => handleReprocess()}
                processing={processing}
                hasImage={image !== null}
                onAutoOptimize={() => {
                  paramSearch.openConfig();
                  setParamSearchOpen(true);
                }}
              />
              <RailSection index={5} title={t('converter:sectionFilaments')}>
                <FilamentConfigPanel
                  presets={filamentPresets}
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
                  whiteBackingLayers={whiteBackingLayers}
                  backingFilament={backingFilament}
                  isConfigValid={isFilamentConfigValid}
                  disabled={processing}
                />
              </RailSection>
              <RailSection index={6} title={t('converter:sectionLibrary')}>
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
              </RailSection>
            </aside>
          )}
        </div>
      </main>

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
        imageDimensions={imageDimensions}
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
              backingFilament,
              maxColors,
              colorThreshold,
              detailSize,
              numColors,
              epsilon,
              minArea,
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
          // Re-apply the model size the search evaluated at, so the reprocessed
          // result matches the card preview (the size is fixed for a whole run
          // and is not part of the per-result params dict).
          handleReprocess(targetLongestEdgeMm, overrides, nextMode);
        }}
      />
    </div>
  );
};

export default Converter;
