/**
 * Custom hook for image processing logic with mode support
 */
import { useState, useEffect, useCallback } from 'react';
import type {
  ColorBlock,
  VectorColorResult,
  ProcessingMode,
  ProcessImageResponse,
  SVGProcessImageResponse,
  FilamentPreset,
} from '../api/types';
import { DEFAULT_PRESETS } from '../api/types';
import { processImage, downloadCSV, downloadSTLV2, downloadSVGSTLV2 } from '../api/client';

export const useImageProcessor = () => {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [processing, setProcessing] = useState(false);
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

  // Filament preset state
  const [filamentPreset, setFilamentPreset] = useState<FilamentPreset>('bambu_cmyk');

  // Process image by calling backend API
  const handleProcessImage = useCallback(async (img: HTMLImageElement, currentMode?: ProcessingMode) => {
    setProcessing(true);
    setError(null);

    const processingMode = currentMode ?? mode;

    try {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx?.drawImage(img, 0, 0);

      const blob = await new Promise<Blob>((resolve) => {
        canvas.toBlob((b) => resolve(b!), 'image/png');
      });

      const file = new File([blob], 'image.png', { type: 'image/png' });

      const result = await processImage(file, {
        mode: processingMode,
        pixelSize,
        pixelParams: processingMode === 'pixel' ? { maxColors, colorThreshold } : undefined,
        svgParams: processingMode === 'svg' ? { epsilon, minArea, numColors } : undefined,
      });

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
      console.error('Error processing image:', err);
      setError(err instanceof Error ? err.message : 'Failed to process image');
    } finally {
      setProcessing(false);
    }
  }, [mode, maxColors, colorThreshold, epsilon, minArea, numColors, pixelSize]);

  // Load default image on mount
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      handleProcessImage(img, 'pixel');
    };
    img.src = 'example.png';
  }, []);

  // Handle image upload
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const img = new Image();
        img.onload = () => {
          setImage(img);
          handleProcessImage(img);
        };
        img.src = event.target?.result as string;
      };
      reader.readAsDataURL(file);
    }
  };

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
      await downloadCSV(colorBlocks);
    } catch (err) {
      console.error('Error downloading CSV:', err);
      setError(err instanceof Error ? err.message : 'Failed to download CSV');
    }
  };

  // Download STL ZIP using V2 API with filament preset
  const handleDownloadSTL = async () => {
    try {
      setError(null);
      setProcessing(true);

      if (mode === 'pixel') {
        await downloadSTLV2({
          colorBlocks,
          layerHeight,
          pixelSize,
          layerCount,
          imageDimensions,
          filamentPreset,
          filamentColors: DEFAULT_PRESETS[filamentPreset],
        });
      } else {
        await downloadSVGSTLV2({
          vectorResults,
          layerHeight,
          pixelSize,
          layerCount,
          imageDimensions,
          filamentPreset,
          filamentColors: DEFAULT_PRESETS[filamentPreset],
        });
      }
    } catch (err) {
      console.error('Error downloading STL:', err);
      setError(err instanceof Error ? err.message : 'Failed to download STL');
    } finally {
      setProcessing(false);
    }
  };

  // Determine if we have results to show
  const hasResults = mode === 'pixel' ? colorBlocks.length > 0 : vectorResults.length > 0;
  const resultCount = mode === 'pixel' ? colorBlocks.length : vectorResults.length;

  return {
    // State
    image,
    processing,
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

    // Filament preset
    filamentPreset,

    // Actions
    setMode: handleModeChange,
    setMaxColors,
    setColorThreshold,
    setEpsilon,
    setMinArea,
    setNumColors,
    setLayerHeight,
    setPixelSize,
    setFilamentPreset,
    handleImageUpload,
    handleReprocess,
    handleDownloadCSV,
    handleDownloadSTL,
  };
};
