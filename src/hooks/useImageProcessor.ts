/**
 * Custom hook for image processing logic with mode support
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import type {
  ColorBlock,
  MappedBlockColor,
  MappedBlendPaletteEntry,
  VectorColorResult,
  ProcessingMode,
  ProcessImageResponse,
  SVGProcessImageResponse,
  ProcessImageParams,
  FilamentPreset,
  FilamentColorConfig,
  FilamentPresetsResponse,
} from '../api/types';
import { isAllTransparentFilaments, isFilamentColorConfig } from '../utils/filaments';
import type { ProcessingStage } from '../components/LoadingSpinner';
import {
  processImage,
  getFilamentPresets,
  simulatePrintPreview,
  downloadCSV,
  downloadSTLV2,
  downloadSVGSTLV2,
  download3MFV2,
  downloadSVG3MFV2,
  downloadPrintSettings,
} from '../api/client';
import { useFilamentStorage } from './useFilamentStorage';
import { buildPrintStack } from '../utils/printStack';

const MIN_FILAMENT_COLORS = 4;
const MAX_FILAMENT_COLORS = 16;
const MIN_COLOR_LAYERS = 4;
const MAX_COLOR_LAYERS = 10;
const DEFAULT_MAX_DIMENSION_MM = 200;
const MIN_PIXEL_SIZE_MM = 0.01;
const MAX_PIXEL_SIZE_MM = 5.0;

const clampPixelSize = (value: number) => Math.max(MIN_PIXEL_SIZE_MM, Math.min(MAX_PIXEL_SIZE_MM, value));

const computeMaxLayerCount = () => MAX_COLOR_LAYERS;

const computeDefaultPixelSize = (widthPx: number, heightPx: number) => {
  const longestSidePx = Math.max(widthPx, heightPx);
  if (longestSidePx <= 0) return null;
  const defaultMaxDimensionMm = Math.min(DEFAULT_MAX_DIMENSION_MM, longestSidePx);
  return clampPixelSize(defaultMaxDimensionMm / longestSidePx);
};

const printableRenderKey = (params: ProcessImageParams) => JSON.stringify(
  params.mode === 'pixel'
    ? {
        mode: params.mode,
        pixelSize: params.pixelSize,
        detailSize: params.detailSize,
        pixelParams: params.pixelParams,
      }
    : params,
);

export const useImageProcessor = () => {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [currentImageFile, setCurrentImageFile] = useState<File | null>(null);
  const [rawImage, setRawImage] = useState<HTMLImageElement | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processingStage, setProcessingStage] = useState<ProcessingStage>('idle');
  const [error, setError] = useState<string | null>(null);

  // Mode selection
  const [mode, setMode] = useState<ProcessingMode>('pixel');

  // Pixel mode state
  const [colorBlocks, setColorBlocks] = useState<ColorBlock[]>([]);
  const [maxColors, setMaxColors] = useState(10);
  const [colorThreshold, setColorThreshold] = useState(50);

  // SVG mode state
  const [vectorResults, setVectorResults] = useState<VectorColorResult[]>([]);
  const [epsilon, setEpsilon] = useState(2.0);
  const [minArea, setMinArea] = useState(4.0);
  const [numColors, setNumColors] = useState(8);

  // Shared state
  const [processedImageUrl, setProcessedImageUrl] = useState<string | null>(null);
  const [segmentationImageUrl, setSegmentationImageUrl] = useState<string | null>(null);
  const [mappedBlockColors, setMappedBlockColors] = useState<MappedBlockColor[]>([]);
  const [mappedBlendPalette, setMappedBlendPalette] = useState<MappedBlendPaletteEntry[]>([]);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const [layerHeight, setLayerHeightValue] = useState(0);
  const layerHeightIsManualRef = useRef(false);
  const setLayerHeight = useCallback((value: number) => {
    layerHeightIsManualRef.current = true;
    setLayerHeightValue(value);
  }, []);
  const [detailSize, setDetailSize] = useState(0.42);
  const [pixelSize, setPixelSize] = useState(0.42);
  const [layerCount, setLayerCount] = useState(MIN_COLOR_LAYERS);
  const [whiteBackingLayers, setWhiteBackingLayers] = useState(0);
  const [backingMode, setBackingMode] = useState<'white' | 'black'>('white');

  const filamentStorage = useFilamentStorage();
  const savedFilamentsRef = useRef(filamentStorage);
  savedFilamentsRef.current = filamentStorage;
  const [filamentCatalog, setFilamentCatalog] = useState<FilamentPresetsResponse | null>(null);
  const [filamentCatalogLoading, setFilamentCatalogLoading] = useState(true);
  const [filamentCatalogError, setFilamentCatalogError] = useState<string | null>(null);
  const [catalogRequest, setCatalogRequest] = useState(0);
  const [filamentPreset, setFilamentPreset] = useState<FilamentPreset | null>(null);
  const [filamentColors, setFilamentColors] = useState<FilamentColorConfig[]>([]);
  const reloadFilamentCatalog = useCallback(() => setCatalogRequest(value => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setFilamentCatalogLoading(true);
    setFilamentCatalogError(null);
    getFilamentPresets(controller.signal).then(catalog => {
      if (controller.signal.aborted) return;
      const initial = catalog.presets.find(preset => preset.name === catalog.defaults.filament_preset);
      if (!initial || initial.colors.length === 0 || !initial.colors.every(isFilamentColorConfig) || catalog.transparency.aggregation !== 'mean') {
        throw new Error('Failed to get filament presets');
      }
      const storage = savedFilamentsRef.current;
      const saved = storage.presets.find(preset => preset.id === storage.lastPresetId);
      const colors = saved ? saved.colors : initial.colors;
      setFilamentCatalog(catalog);
      setFilamentPreset(saved ? null : initial.name);
      setFilamentColors(structuredClone(colors));
      setWhiteBackingLayers(catalog.defaults.backing_layers);
      setLayerHeightValue(isAllTransparentFilaments(colors, catalog.transparency)
        ? catalog.defaults.transparent_layer_height_mm : catalog.defaults.regular_layer_height_mm);
    }).catch(err => {
      if (!controller.signal.aborted) setFilamentCatalogError(err instanceof Error ? err.message : 'Failed to get filament presets');
    }).finally(() => {
      if (!controller.signal.aborted) setFilamentCatalogLoading(false);
    });
    return () => controller.abort();
  }, [catalogRequest]);

  const allTransparent = useMemo(
    () => filamentCatalog !== null && isAllTransparentFilaments(filamentColors, filamentCatalog.transparency),
    [filamentColors, filamentCatalog]
  );
  const previousTransparentRef = useRef(allTransparent);
  useEffect(() => {
    if (!filamentCatalog || previousTransparentRef.current === allTransparent) return;
    previousTransparentRef.current = allTransparent;
    const { regular_layer_height_mm: regular, transparent_layer_height_mm: transparent } = filamentCatalog.defaults;
    if (!layerHeightIsManualRef.current) {
      setLayerHeightValue(allTransparent ? transparent : regular);
    }
  }, [allTransparent, filamentCatalog]);

  // Physical size is derived directly from pixelSize and image dimensions.
  const targetWidth = imageDimensions.width > 0
    ? Math.round(imageDimensions.width * pixelSize * 100) / 100
    : 0;
  const targetHeight = imageDimensions.height > 0
    ? Math.round(imageDimensions.height * pixelSize * 100) / 100
    : 0;
  const maxDimension = Math.max(targetWidth, targetHeight);

  const setMaxDimension = useCallback((dimensionMm: number) => {
    const clampedDimension = Math.max(1, Math.min(500, dimensionMm));
    const longestSidePx = Math.max(imageDimensions.width, imageDimensions.height);
    if (longestSidePx <= 0) return;
    setPixelSize(clampPixelSize(clampedDimension / longestSidePx));
  }, [imageDimensions.height, imageDimensions.width]);

  const handleSetPixelSize = useCallback((value: number) => {
    setPixelSize(clampPixelSize(value));
  }, []);

  // Printable detail and model scale are independent physical settings.
  const handleSetDetailSize = useCallback((value: number) => {
    setDetailSize(value);
  }, []);

  // AbortController ref for cancelling in-flight image processing requests
  const processAbortRef = useRef<AbortController | null>(null);
  const previewAbortRef = useRef<AbortController | null>(null);
  const skipNextPreviewRefreshRef = useRef(false);
  const requestedRenderKeyRef = useRef<string | null>(null);
  const completedRenderKeyRef = useRef<string | null>(null);
  // Set to true when handleApplyEdit cannot determine image dimensions upfront;
  // handleProcessImage will then apply the default after the API returns dimensions.
  const shouldApplyDefaultMaxDimensionRef = useRef(false);

  // Load a built-in preset into filamentColors
  const loadPreset = useCallback((preset: FilamentPreset) => {
    const selected = filamentCatalog?.presets.find(entry => entry.name === preset);
    if (!selected) return;
    setFilamentPreset(preset);
    setFilamentColors(structuredClone(selected.colors));
    filamentStorage.setLastPresetId(null);
  }, [filamentStorage, filamentCatalog]);

  // Load a saved (custom) preset's colors into the editor
  const loadSavedPresetColors = useCallback((colors: FilamentColorConfig[]) => {
    setFilamentPreset(null);
    setFilamentColors(structuredClone(colors));
  }, []);

  // Update a single filament color by index
  const updateFilamentColor = useCallback((index: number, updated: FilamentColorConfig) => {
    setFilamentColors(prev => {
      const next = [...prev];
      next[index] = structuredClone(updated);
      return next;
    });
    setFilamentPreset(null);
  }, []);

  // Add a new filament color
  const addFilamentColor = useCallback(() => {
    setFilamentColors(prev => {
      if (prev.length >= MAX_FILAMENT_COLORS) return prev;
      const labels = new Set(prev.map(color => color.name[0].toUpperCase()));
      let code = 'A'.charCodeAt(0);
      while (labels.has(String.fromCharCode(code))) code++;
      return [...prev, {
        name: String.fromCharCode(code),
        hex: '#808080',
        transmission_distance: 0,
      }];
    });
    setFilamentPreset(null);
  }, []);

  // Remove a filament color by index
  const removeFilamentColor = useCallback((index: number) => {
    setFilamentColors(prev => {
      if (prev.length <= MIN_FILAMENT_COLORS) return prev;
      return prev.filter((_, i) => i !== index);
    });
    setFilamentPreset(null);
  }, []);

  // Validate filament config
  const isFilamentConfigValid = useMemo(() => {
    if (filamentColors.length < MIN_FILAMENT_COLORS) return false;
    if (filamentColors.length > MAX_FILAMENT_COLORS) return false;

    if (!filamentCatalog || !filamentColors.every(isFilamentColorConfig)) return false;
    const labels = filamentColors.map(c => c.name[0].toUpperCase());
    if (new Set(labels).size !== labels.length) return false;
    const hexValues = filamentColors.map(c => c.hex.toLowerCase());
    if (new Set(hexValues).size !== hexValues.length) return false;

    return true;
  }, [filamentColors, filamentCatalog]);

  const filamentRequestPayload = useMemo(
    () => (filamentPreset ? { filamentPreset } : { filamentColors }),
    [filamentColors, filamentPreset]
  );

  const maxLayerCount = useMemo(() => computeMaxLayerCount(), []);

  const handleSetLayerCount = useCallback((value: number) => {
    setLayerCount(Math.max(MIN_COLOR_LAYERS, Math.min(maxLayerCount, value)));
  }, [maxLayerCount]);

  useEffect(() => {
    setLayerCount(prev => Math.min(prev, maxLayerCount));
  }, [maxLayerCount]);

  const makeProcessParams = useCallback((currentMode?: ProcessingMode, overridePixelSize?: number, overrides?: Partial<{
    maxColors: number; colorThreshold: number; epsilon: number; minArea: number; numColors: number;
    detailSize: number; whiteBackingLayers: number;
  }>): ProcessImageParams => {
    const processingMode = currentMode ?? mode;
    return {
      mode: processingMode,
      pixelSize: overridePixelSize ?? pixelSize,
      layerHeight,
      layerCount,
      whiteBackingLayers: overrides?.whiteBackingLayers ?? whiteBackingLayers,
      backingMode,
      ...filamentRequestPayload,
      detailSize: overrides?.detailSize ?? detailSize,
      pixelParams: processingMode === 'pixel'
        ? { maxColors: overrides?.maxColors ?? maxColors, colorThreshold: overrides?.colorThreshold ?? colorThreshold }
        : undefined,
      svgParams: processingMode === 'svg'
        ? { epsilon: overrides?.epsilon ?? epsilon, minArea: overrides?.minArea ?? minArea, numColors: overrides?.numColors ?? numColors }
        : undefined,
    };
  }, [mode, pixelSize, detailSize, maxColors, colorThreshold, epsilon, minArea, numColors,
    layerHeight, layerCount, whiteBackingLayers, backingMode, filamentRequestPayload]);

  // Process image by calling backend API
  const handleProcessImage = useCallback(async (img: HTMLImageElement, currentMode?: ProcessingMode, overridePixelSize?: number, overrides?: Partial<{
    maxColors: number; colorThreshold: number; epsilon: number; minArea: number; numColors: number;
    detailSize: number; whiteBackingLayers: number;
  }>) => {
    if (!isFilamentConfigValid) {
      setError('Invalid filament color configuration');
      return;
    }
    // Abort any in-flight processing request
    if (processAbortRef.current) {
      processAbortRef.current.abort();
    }

    const controller = new AbortController();
    processAbortRef.current = controller;

    setProcessing(true);
    setProcessingStage('uploading');
    setError(null);

    const requestParams = makeProcessParams(currentMode, overridePixelSize, overrides);
    const processingMode = requestParams.mode;
    const requestKey = printableRenderKey(requestParams);
    requestedRenderKeyRef.current = requestKey;

    try {
      const maxDimension = 4096;
      if (img.width > maxDimension || img.height > maxDimension) {
        setError(`Image too large (${img.width}x${img.height}). Maximum dimension is ${maxDimension}px.`);
        setProcessing(false);
        setProcessingStage('idle');
        return;
      }

      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        throw new Error('Failed to get 2D canvas context');
      }
      ctx.drawImage(img, 0, 0);

      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((b) => {
          if (b) resolve(b);
          else reject(new Error('Failed to create blob from canvas'));
        }, 'image/png');
      });

      const file = new File([blob], 'image.png', { type: 'image/png' });

      setProcessingStage('processing');

      const result = await processImage(file, requestParams, controller.signal);

      // Only update state if this request wasn't aborted
      if (controller.signal.aborted) return;
      completedRenderKeyRef.current = requestKey;

      setCurrentImageFile(file);
      setImageDimensions(result.imageDimensions);

      // Sync backend-confirmed parameters. pixelSize remains the actual model pitch.
      if (result.pixelSize !== undefined && result.pixelSize !== null) {
        setPixelSize(result.pixelSize);
      }
      if (result.detailSize !== undefined && result.detailSize !== null) {
        setDetailSize(result.detailSize);
      }
      // Fallback: if handleApplyEdit couldn't compute default upfront (image dimensions
      // were 0), compute it now from the backend-returned dimensions.
      if (shouldApplyDefaultMaxDimensionRef.current) {
        const defaultPixelSize = computeDefaultPixelSize(
          result.imageDimensions.width,
          result.imageDimensions.height,
        );
        if (defaultPixelSize !== null) {
          setPixelSize(defaultPixelSize);
        }
        shouldApplyDefaultMaxDimensionRef.current = false;
      }

      if (processingMode === 'pixel') {
        const pixelResult = result as ProcessImageResponse;
        setProcessedImageUrl(pixelResult.processedImage);
        setSegmentationImageUrl(pixelResult.segmentationImage);
        setMappedBlockColors(pixelResult.mappedBlockColors);
        setMappedBlendPalette(pixelResult.mappedBlendPalette);
        setColorBlocks(pixelResult.colorBlocks);
        skipNextPreviewRefreshRef.current = true;
        setVectorResults([]);
      } else {
        const svgResult = result as SVGProcessImageResponse;
        setProcessedImageUrl(svgResult.processedImage);
        setSegmentationImageUrl(svgResult.segmentationImage);
        setMappedBlockColors([]);
        setMappedBlendPalette(svgResult.mappedBlendPalette);
        setVectorResults(svgResult.vectorResults);
        setColorBlocks([]);
      }

    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (controller.signal.aborted) return;
      console.error('Error processing image:', err);
      setError(err instanceof Error ? err.message : 'Failed to process image');
    } finally {
      if (!controller.signal.aborted) {
        setProcessing(false);
        setProcessingStage('idle');
      }
    }
  }, [makeProcessParams, isFilamentConfigValid]);

  const currentRenderKey = printableRenderKey(makeProcessParams());
  const renderReady = completedRenderKeyRef.current === currentRenderKey;
  const hasProcessedGeometry = mode === 'pixel' ? colorBlocks.length > 0 : vectorResults.length > 0;

  // Changes to physical geometry require a new material assignment. SVG
  // mapping changes also require a new printable preview before export.
  useEffect(() => {
    if (!image || !hasProcessedGeometry || !isFilamentConfigValid) return;
    if (completedRenderKeyRef.current === currentRenderKey || requestedRenderKeyRef.current === currentRenderKey) return;
    const timer = window.setTimeout(() => {
      void handleProcessImage(image);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [image, hasProcessedGeometry, isFilamentConfigValid, currentRenderKey, handleProcessImage]);


  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (processAbortRef.current) {
        processAbortRef.current.abort();
      }
      if (previewAbortRef.current) {
        previewAbortRef.current.abort();
      }
    };
  }, []);

  // Load a File into editing mode
  const handleFile = (file: File) => {
    const validTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'];
    if (!validTypes.includes(file.type)) {
      setError(`Unsupported file type: ${file.type}. Please upload a PNG, JPEG, GIF, WebP, or BMP image.`);
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        setRawImage(img);
        setIsEditing(true);
      };
      img.onerror = () => {
        setError('Failed to load image. The file may be corrupted or not a valid image.');
      };
      img.src = event.target?.result as string;
    };
    reader.onerror = () => {
      setError('Failed to read file.');
    };
    reader.readAsDataURL(file);
  };

  // Handle image upload from file input
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    handleFile(file);
    // Reset input to allow re-selecting the same file
    e.target.value = '';
  };

  // Apply edited image from ImageEditor and start processing
  const handleApplyEdit = useCallback((editedImg: HTMLImageElement) => {
    // Predict the backend-downscaled dimensions (MAX_PROCESSING_DIMENSION=4096)
    // so we can compute the correct default pixelSize upfront, matching what the
    // backend will actually return in imageDimensions.
    const imgW = editedImg.naturalWidth || editedImg.width;
    const imgH = editedImg.naturalHeight || editedImg.height;
    const BACKEND_MAX_DIM = 4096;
    let processedW = imgW;
    let processedH = imgH;
    if (imgW > 0 && imgH > 0 && Math.max(imgW, imgH) > BACKEND_MAX_DIM) {
      const scale = BACKEND_MAX_DIM / Math.max(imgW, imgH);
      processedW = Math.round(imgW * scale);
      processedH = Math.round(imgH * scale);
    }
    const defaultPixelSize = processedW > 0 && processedH > 0
      ? computeDefaultPixelSize(processedW, processedH)
      : null;
    if (defaultPixelSize !== null) {
      setPixelSize(defaultPixelSize);
    } else {
      shouldApplyDefaultMaxDimensionRef.current = true;
    }
    setImage(editedImg);
    setRawImage(null);
    setIsEditing(false);
    handleProcessImage(editedImg, undefined, defaultPixelSize ?? undefined);
  }, [handleProcessImage]);

  // Cancel editing and revert to previous state
  const handleCancelEdit = useCallback(() => {
    setRawImage(null);
    setIsEditing(false);
  }, []);

  // Reprocess image with current parameters
  const handleReprocess = (
    overridePixelSize?: number,
    overrides?: Parameters<typeof handleProcessImage>[3],
    modeOverride?: ProcessingMode,
  ) => {
    // onClick handlers forward the MouseEvent as the first argument; guard
    // against non-number values leaking into the pixelSize override.
    const pixelSizeOverride = typeof overridePixelSize === 'number' ? overridePixelSize : undefined;
    if (image) {
      handleProcessImage(image, modeOverride, pixelSizeOverride, overrides);
    }
  };

  // Handle mode change
  const handleModeChange = (newMode: ProcessingMode) => {
    setMode(newMode);
    if (image) {
      handleProcessImage(image, newMode);
    }
  };

  // Download CSV (only pixel mode)
  const handleDownloadCSV = async () => {
    if (mode !== 'pixel') {
      setError('CSV download is only available in Pixel mode');
      return;
    }

    try {
      setError(null);
      setProcessing(true);
      setProcessingStage('generating');
      await downloadCSV(colorBlocks);
    } catch (err) {
      console.error('Error downloading CSV:', err);
      setError(err instanceof Error ? err.message : 'Failed to download CSV');
    } finally {
      setProcessing(false);
      setProcessingStage('idle');
    }
  };

  // Download STL ZIP using V2 API with filament colors
  const handleDownloadSTL = async () => {
    if (!isFilamentConfigValid) {
      setError('Invalid filament color configuration');
      return;
    }

    try {
      setError(null);
      setProcessing(true);
      setProcessingStage('generating');

      const commonParams = {
        layerHeight,
        pixelSize,
        layerCount,
        whiteBackingLayers,
        backingMode,
        imageDimensions,
        detailSize,
        ...filamentRequestPayload,
      };

      if (mode === 'pixel') {
        await downloadSTLV2({ colorBlocks, ...commonParams });
      } else {
        await downloadSVGSTLV2({ vectorResults, ...commonParams });
      }
    } catch (err) {
      console.error('Error downloading STL:', err);
      setError(err instanceof Error ? err.message : 'Failed to download STL');
    } finally {
      setProcessing(false);
      setProcessingStage('idle');
    }
  };

  // Download 3MF file using V2 API (pixel and SVG modes)
  const handleDownload3MF = async () => {
    if (!isFilamentConfigValid) {
      setError('Invalid filament color configuration');
      return;
    }

    try {
      setError(null);
      setProcessing(true);
      setProcessingStage('generating');

      const commonParams = {
        layerHeight,
        pixelSize,
        layerCount,
        whiteBackingLayers,
        backingMode,
        imageDimensions,
        detailSize,
        ...filamentRequestPayload,
      };

      if (mode === 'pixel') {
        await download3MFV2({ colorBlocks, ...commonParams });
      } else {
        await downloadSVG3MFV2({ vectorResults, ...commonParams });
      }
    } catch (err) {
      console.error('Error downloading 3MF:', err);
      setError(err instanceof Error ? err.message : 'Failed to download 3MF');
    } finally {
      setProcessing(false);
      setProcessingStage('idle');
    }
  };

  // Download print settings JSON
  const handleDownloadPrintSettings = async () => {
    if (!isFilamentConfigValid) {
      setError('Invalid filament color configuration');
      return;
    }

    try {
      setError(null);
      setProcessing(true);
      setProcessingStage('generating');
      await downloadPrintSettings({
        layerHeight,
        pixelSize,
        layerCount,
        whiteBackingLayers,
        backingMode,
        imageDimensions,
        detailSize,
        ...filamentRequestPayload,
      });
    } catch (err) {
      console.error('Error downloading print settings:', err);
      setError(err instanceof Error ? err.message : 'Failed to download print settings');
    } finally {
      setProcessing(false);
      setProcessingStage('idle');
    }
  };

  const refreshSimulatedPreview = useCallback(async (blocks: ColorBlock[]) => {
    if (mode !== 'pixel' || blocks.length === 0 || imageDimensions.width === 0 || !isFilamentConfigValid) {
      return;
    }

    if (previewAbortRef.current) {
      previewAbortRef.current.abort();
    }

    const controller = new AbortController();
    previewAbortRef.current = controller;

    try {
      const result = await simulatePrintPreview({
        colorBlocks: blocks,
        imageDimensions,
        layerHeight,
        layerCount,
        whiteBackingLayers,
        backingMode,
        ...filamentRequestPayload,
      }, controller.signal);
      if (controller.signal.aborted) return;
      setProcessedImageUrl(result.processedImage);
      setMappedBlockColors(result.mappedBlockColors);
      setMappedBlendPalette(result.mappedBlendPalette);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (controller.signal.aborted) return;
      console.error('Error refreshing simulated preview:', err);
      setError(err instanceof Error ? err.message : 'Failed to refresh simulated preview');
    }
  }, [
    mode,
    imageDimensions,
    isFilamentConfigValid,
    layerHeight,
    layerCount,
    filamentRequestPayload,
    whiteBackingLayers,
    backingMode,
  ]);

  // Keep the simulated print preview in sync with manual edits and filament changes.
  useEffect(() => {
    if (mode !== 'pixel') return;
    if (colorBlocks.length === 0 || imageDimensions.width === 0) return;
    if (skipNextPreviewRefreshRef.current) {
      skipNextPreviewRefreshRef.current = false;
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshSimulatedPreview(colorBlocks);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [mode, colorBlocks, imageDimensions, layerHeight, layerCount, whiteBackingLayers, backingMode, filamentRequestPayload, refreshSimulatedPreview]);

  const printStack = useMemo(
    () => buildPrintStack(
      layerCount,
      layerHeight,
      whiteBackingLayers,
      backingMode,
    ),
[layerCount, layerHeight, whiteBackingLayers, backingMode]
  );

  // Update a color block's RGB/hex values (manual color adjustment)
  const updateColorBlock = useCallback((index: number, newHex: string) => {
    setColorBlocks(prev => {
      if (index < 0 || index >= prev.length) return prev;
      const hex = newHex.toUpperCase();
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      const next = [...prev];
      next[index] = { ...next[index], r, g, b, hex };
      return next;
    });
    // Preview auto-regenerated via useEffect when colorBlocks changes
  }, []);

  // Merge one color block into another (reassign all pixels)
  const mergeColorBlocks = useCallback((sourceIndex: number, targetIndex: number) => {
    setColorBlocks(prev => {
      if (sourceIndex === targetIndex) return prev;
      if (sourceIndex < 0 || sourceIndex >= prev.length) return prev;
      if (targetIndex < 0 || targetIndex >= prev.length) return prev;
      const source = prev[sourceIndex];
      const target = prev[targetIndex];
      const merged: ColorBlock = {
        ...target,
        count: target.count + source.count,
        pixels: [...target.pixels, ...source.pixels],
      };
      const next = prev.filter((_, i) => i !== sourceIndex);
      const adjustedTargetIndex = targetIndex > sourceIndex ? targetIndex - 1 : targetIndex;
      next[adjustedTargetIndex] = merged;
      return next;
    });
    // Preview auto-regenerated via useEffect when colorBlocks changes
  }, []);

  // Delete a color block by merging its pixels into the nearest remaining color
  const deleteColorBlock = useCallback((index: number) => {
    setColorBlocks(prev => {
      if (prev.length <= 1) return prev;
      if (index < 0 || index >= prev.length) return prev;
      const deleted = prev[index];
      const remaining = prev.filter((_, i) => i !== index);

      let nearestIdx = 0;
      let minDist = Infinity;
      for (let i = 0; i < remaining.length; i++) {
        const c = remaining[i];
        const dist = Math.sqrt(
          (c.r - deleted.r) ** 2 +
          (c.g - deleted.g) ** 2 +
          (c.b - deleted.b) ** 2
        );
        if (dist < minDist) {
          minDist = dist;
          nearestIdx = i;
        }
      }

      const target = remaining[nearestIdx];
      remaining[nearestIdx] = {
        ...target,
        count: target.count + deleted.count,
        pixels: [...target.pixels, ...deleted.pixels],
      };
      return remaining;
    });
    // Preview auto-regenerated via useEffect when colorBlocks changes
  }, []);

  // Determine if we have results to show
  const hasResults = mode === 'pixel' ? colorBlocks.length > 0 : vectorResults.length > 0;
  const resultCount = mode === 'pixel' ? colorBlocks.length : vectorResults.length;

  return {
    // State
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
    imageDimensions,
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
    whiteBackingLayers,
    backingMode,
    setBackingMode,
    targetWidth,
    targetHeight,
    maxDimension,
    maxLayerCount,
    printStack,

    // Filament state
    filamentPresets: filamentCatalog?.presets ?? [],
    filamentCatalogLoading,
    filamentCatalogError,
    reloadFilamentCatalog,
    filamentPreset,
    filamentColors,
    isFilamentConfigValid,

    // Filament storage (saved presets)
    filamentStorage,

    // Actions
    setMode: handleModeChange,
    setMaxColors,
    setColorThreshold,
    setEpsilon,
    setMinArea,
    setNumColors,
    setLayerHeight,
    allTransparent,
    setLayerCount: handleSetLayerCount,
    setPixelSize: handleSetPixelSize,
    setDetailSize: handleSetDetailSize,
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
  };
};
