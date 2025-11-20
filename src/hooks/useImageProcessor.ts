/**
 * Custom hook for image processing logic
 */
import { useState, useEffect } from 'react';
import type { ColorBlock } from '../api/types';
import { processImage, downloadCSV, downloadSTL } from '../api/client';

export const useImageProcessor = () => {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [processing, setProcessing] = useState(false);
  const [colorBlocks, setColorBlocks] = useState<ColorBlock[]>([]);
  const [processedImageUrl, setProcessedImageUrl] = useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const [maxColors, setMaxColors] = useState(10);
  const [colorThreshold, setColorThreshold] = useState(50);
  const [layerHeight, setLayerHeight] = useState(0.08);
  const [pixelSize, setPixelSize] = useState(0.08);
  const [layerCount] = useState(4);
  const [error, setError] = useState<string | null>(null);

  // Load default image on mount
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      handleProcessImage(img);
    };
    img.src = 'example.png';
  }, []);

  // Process image by calling backend API
  const handleProcessImage = async (img: HTMLImageElement) => {
    setProcessing(true);
    setError(null);

    try {
      // Convert image to blob
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx?.drawImage(img, 0, 0);

      const blob = await new Promise<Blob>((resolve) => {
        canvas.toBlob((b) => resolve(b!), 'image/png');
      });

      // Create File object from blob
      const file = new File([blob], 'image.png', { type: 'image/png' });

      // Call backend API
      const result = await processImage(file, {
        maxColors,
        colorThreshold,
        pixelSize,
      });

      // Update state with results
      setColorBlocks(result.colorBlocks);
      setProcessedImageUrl(result.processedImage);
      setImageDimensions(result.imageDimensions);

    } catch (err) {
      console.error('Error processing image:', err);
      setError(err instanceof Error ? err.message : 'Failed to process image');
    } finally {
      setProcessing(false);
    }
  };

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

  // Download CSV
  const handleDownloadCSV = async () => {
    try {
      setError(null);
      await downloadCSV(colorBlocks);
    } catch (err) {
      console.error('Error downloading CSV:', err);
      setError(err instanceof Error ? err.message : 'Failed to download CSV');
    }
  };

  // Download STL ZIP
  const handleDownloadSTL = async () => {
    try {
      setError(null);
      setProcessing(true);
      await downloadSTL({
        colorBlocks,
        layerHeight,
        pixelSize,
        layerCount,
        imageDimensions,
      });
    } catch (err) {
      console.error('Error downloading STL:', err);
      setError(err instanceof Error ? err.message : 'Failed to download STL');
    } finally {
      setProcessing(false);
    }
  };

  return {
    // State
    image,
    processing,
    colorBlocks,
    processedImageUrl,
    imageDimensions,
    maxColors,
    colorThreshold,
    layerHeight,
    pixelSize,
    error,

    // Actions
    setMaxColors,
    setColorThreshold,
    setLayerHeight,
    setPixelSize,
    handleImageUpload,
    handleReprocess,
    handleDownloadCSV,
    handleDownloadSTL,
  };
};
