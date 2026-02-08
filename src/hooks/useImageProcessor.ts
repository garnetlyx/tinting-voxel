/**
 * Custom hook for image processing logic with mode support
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import type {
  ColorBlock,
  VectorColorResult,
  ProcessingMode,
  ProcessImageResponse,
  SVGProcessImageResponse,
  FilamentPreset,
  FilamentColorConfig,
} from '../api/types';
import { DEFAULT_PRESETS } from '../api/types';
import type { ProcessingStage } from '../components/LoadingSpinner';
import { processImage, downloadCSV, downloadSTLV2, downloadSVGSTLV2, download3MFV2, downloadPrintSettings } from '../api/client';
import { useFilamentStorage } from './useFilamentStorage';

const MIN_FILAMENT_COLORS = 4;
const MAX_FILAMENT_COLORS = 16;

export const useImageProcessor = () => {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
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
  const [minArea, setMinArea] = useState(100);
  const [numColors, setNumColors] = useState(8);

  // Shared state
  const [processedImageUrl, setProcessedImageUrl] = useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const [layerHeight, setLayerHeight] = useState(0.08);
  const [pixelSize, setPixelSize] = useState(0.08);
  const [layerCount] = useState(4);

  // Base plate options
  const [basePlateThickness, setBasePlateThickness] = useState(0.0);

  // Double-sided print
  const [doubleSided, setDoubleSided] = useState(false);

  // Filament color state
  const [filamentPreset, setFilamentPreset] = useState<FilamentPreset | null>('bambu_cmyk');
  const [filamentColors, setFilamentColors] = useState<FilamentColorConfig[]>(
    [...DEFAULT_PRESETS['bambu_cmyk']]
  );

  // Filament preset storage (localStorage persistence)
  const filamentStorage = useFilamentStorage();

  // Computed target physical width in mm (derived from imageDimensions and pixelSize)
  const targetWidth = imageDimensions.width > 0
    ? Math.round(imageDimensions.width * pixelSize * 100) / 100
    : 0;
  const targetHeight = imageDimensions.height > 0
    ? Math.round(imageDimensions.height * pixelSize * 100) / 100
    : 0;

  // Set target physical width and derive pixelSize from it
  const setTargetWidth = useCallback((widthMm: number) => {
    if (imageDimensions.width > 0 && widthMm > 0) {
      const newPixelSize = Math.round((widthMm / imageDimensions.width) * 10000) / 10000;
      setPixelSize(Math.max(0.01, Math.min(2.0, newPixelSize)));
    }
  }, [imageDimensions.width]);

  // AbortController ref for cancelling in-flight image processing requests
  const processAbortRef = useRef<AbortController | null>(null);

  // Load a built-in preset into filamentColors
  const loadPreset = useCallback((preset: FilamentPreset) => {
    setFilamentPreset(preset);
    setFilamentColors([...DEFAULT_PRESETS[preset]]);
    filamentStorage.setLastPresetId(null);
  }, [filamentStorage]);

  // Load a saved (custom) preset's colors into the editor
  const loadSavedPresetColors = useCallback((colors: FilamentColorConfig[]) => {
    setFilamentPreset(null);
    setFilamentColors([...colors]);
  }, []);

  // Update a single filament color by index
  const updateFilamentColor = useCallback((index: number, updated: FilamentColorConfig) => {
    setFilamentColors(prev => {
      const next = [...prev];
      next[index] = updated;
      return next;
    });
    setFilamentPreset(null);
  }, []);

  // Add a new filament color
  const addFilamentColor = useCallback(() => {
    setFilamentColors(prev => {
      if (prev.length >= MAX_FILAMENT_COLORS) return prev;
      return [...prev, { name: '', hex: '#808080', transmission_distance: 5.0 }];
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

    // All names must be non-empty
    if (filamentColors.some(c => !c.name.trim())) return false;

    // Unique first letters
    const labels = filamentColors.map(c => c.name[0]?.toUpperCase());
    if (new Set(labels).size !== labels.length) return false;

    // Validate hex format (#RRGGBB)
    const hexRegex = /^#[0-9a-fA-F]{6}$/;
    if (filamentColors.some(c => !hexRegex.test(c.hex))) return false;

    // Unique hex values
    const hexValues = filamentColors.map(c => c.hex.toLowerCase());
    if (new Set(hexValues).size !== hexValues.length) return false;

    // Transmission distance must be positive
    if (filamentColors.some(c => c.transmission_distance <= 0)) return false;

    return true;
  }, [filamentColors]);

  // Process image by calling backend API
  const handleProcessImage = useCallback(async (img: HTMLImageElement, currentMode?: ProcessingMode) => {
    // Abort any in-flight processing request
    if (processAbortRef.current) {
      processAbortRef.current.abort();
    }

    const controller = new AbortController();
    processAbortRef.current = controller;

    setProcessing(true);
    setProcessingStage('uploading');
    setError(null);

    const processingMode = currentMode ?? mode;

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

      const result = await processImage(file, {
        mode: processingMode,
        pixelSize,
        pixelParams: processingMode === 'pixel' ? { maxColors, colorThreshold } : undefined,
        svgParams: processingMode === 'svg' ? { epsilon, minArea, numColors } : undefined,
      }, controller.signal);

      // Only update state if this request wasn't aborted
      if (controller.signal.aborted) return;

      setProcessedImageUrl(result.processedImage);
      setImageDimensions(result.imageDimensions);

      if (processingMode === 'pixel') {
        const pixelResult = result as ProcessImageResponse;
        setColorBlocks(pixelResult.colorBlocks);
        setVectorResults([]);
      } else {
        const svgResult = result as SVGProcessImageResponse;
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
  }, [mode, maxColors, colorThreshold, epsilon, minArea, numColors, pixelSize]);

  // Auto-load last used saved preset on mount
  useEffect(() => {
    const lastId = filamentStorage.lastPresetId;
    if (lastId) {
      const saved = filamentStorage.presets.find(p => p.id === lastId);
      if (saved) {
        setFilamentPreset(null);
        setFilamentColors([...saved.colors]);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only on mount

  // Load default image on mount
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      handleProcessImage(img, 'pixel');
    };
    img.onerror = () => {
      console.warn('Default example image not found (example.png). Upload an image to get started.');
    };
    img.src = 'example.png';
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (processAbortRef.current) {
        processAbortRef.current.abort();
      }
    };
  }, []);

  // Handle image upload — enter editing mode for crop/resize
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const validTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'];
    if (!validTypes.includes(file.type)) {
      setError(`Unsupported file type: ${file.type}. Please upload a PNG, JPEG, GIF, WebP, or BMP image.`);
      // Reset input to allow re-selecting the same file
      e.target.value = '';
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
        // Reset input to allow re-selecting the same file
        e.target.value = '';
      };
      img.src = event.target?.result as string;
    };
    reader.onerror = () => {
      setError('Failed to read file.');
      // Reset input to allow re-selecting the same file
      e.target.value = '';
    };
    reader.readAsDataURL(file);
  };

  // Apply edited image from ImageEditor and start processing
  const handleApplyEdit = useCallback((editedImg: HTMLImageElement) => {
    setImage(editedImg);
    setRawImage(null);
    setIsEditing(false);
    handleProcessImage(editedImg);
  }, [handleProcessImage]);

  // Cancel editing and revert to previous state
  const handleCancelEdit = useCallback(() => {
    setRawImage(null);
    setIsEditing(false);
  }, []);

  // Reprocess image with current parameters
  const handleReprocess = () => {
    if (image) {
      handleProcessImage(image);
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
        imageDimensions,
        filamentColors,
        basePlateThickness: basePlateThickness > 0 ? basePlateThickness : undefined,
      };

      if (mode === 'pixel') {
        await downloadSTLV2({ colorBlocks, ...commonParams, ...(doubleSided ? { doubleSided } : {}) });
      } else {
        await downloadSVGSTLV2({ vectorResults, ...commonParams, ...(doubleSided ? { doubleSided } : {}) });
      }
    } catch (err) {
      console.error('Error downloading STL:', err);
      setError(err instanceof Error ? err.message : 'Failed to download STL');
    } finally {
      setProcessing(false);
      setProcessingStage('idle');
    }
  };

  // Download 3MF file using V2 API (pixel mode only)
  const handleDownload3MF = async () => {
    if (!isFilamentConfigValid) {
      setError('Invalid filament color configuration');
      return;
    }
    if (mode !== 'pixel') {
      setError('3MF download is only available in Pixel mode');
      return;
    }

    try {
      setError(null);
      setProcessing(true);
      setProcessingStage('generating');

      await download3MFV2({
        colorBlocks,
        layerHeight,
        pixelSize,
        layerCount,
        imageDimensions,
        filamentColors,
        basePlateThickness: basePlateThickness > 0 ? basePlateThickness : undefined,
        ...(doubleSided ? { doubleSided } : {}),
      });
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
        imageDimensions,
        filamentColors,
        basePlateThickness: basePlateThickness > 0 ? basePlateThickness : undefined,
      });
    } catch (err) {
      console.error('Error downloading print settings:', err);
      setError(err instanceof Error ? err.message : 'Failed to download print settings');
    } finally {
      setProcessing(false);
      setProcessingStage('idle');
    }
  };

  // Regenerate the processed image preview from current colorBlocks
  const regenerateProcessedImage = useCallback((blocks: ColorBlock[]) => {
    if (blocks.length === 0 || imageDimensions.width === 0) return;
    const { width, height } = imageDimensions;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    for (const block of blocks) {
      ctx.fillStyle = block.hex;
      for (const pixel of block.pixels) {
        if (pixel.x >= 0 && pixel.x < width && pixel.y >= 0 && pixel.y < height) {
          ctx.fillRect(pixel.x, pixel.y, 1, 1);
        }
      }
    }

    setProcessedImageUrl(canvas.toDataURL('image/png'));
  }, [imageDimensions]);

  // Regenerate preview when colorBlocks change (for manual color adjustments)
  useEffect(() => {
    if (colorBlocks.length > 0) {
      regenerateProcessedImage(colorBlocks);
    }
  }, [colorBlocks, regenerateProcessedImage]);

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
    rawImage,
    isEditing,
    processing,
    processingStage,
    error,
    mode,
    colorBlocks,
    vectorResults,
    processedImageUrl,
    imageDimensions,
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

    // Filament state
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
    setPixelSize,
    setTargetWidth,
    setBasePlateThickness,
    setDoubleSided,
    loadPreset,
    loadSavedPresetColors,
    updateFilamentColor,
    addFilamentColor,
    removeFilamentColor,
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
