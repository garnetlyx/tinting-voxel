import React, { useState, useRef, useEffect } from 'react';
import { Upload, Download, Settings, Palette } from 'lucide-react';
import type { ColorBlock } from './api/types';
import { processImage, downloadCSV, downloadSTL } from './api/client';

const ImageToMeshConverter = () => {
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
  const [showSettings, setShowSettings] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load default image on component mount
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      handleProcessImage(img);
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-8">
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

          {showSettings && (
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
                  onChange={(e) => setMaxColors(parseInt(e.target.value))}
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
                  onChange={(e) => setColorThreshold(parseInt(e.target.value))}
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
                  onChange={(e) => setLayerHeight(parseFloat(e.target.value))}
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
                  onChange={(e) => setPixelSize(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              {image && (
                <button
                  onClick={handleReprocess}
                  disabled={processing}
                  className="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:bg-gray-400"
                >
                  {processing ? 'Processing...' : 'Reprocess'}
                </button>
              )}
            </div>
          )}

          <div className="mb-8">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-4 border-2 border-dashed border-gray-300 rounded-xl hover:border-purple-400 hover:bg-purple-50 transition-all flex items-center justify-center gap-3 text-gray-600 hover:text-purple-600"
            >
              <Upload className="w-6 h-6" />
              <span className="font-medium">Click to Upload Image</span>
            </button>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          {processing && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Processing...</p>
            </div>
          )}

          {!processing && colorBlocks.length > 0 && (
            <div>
              {/* Before/After Preview */}
              <div className="mb-8">
                <h2 className="text-xl font-semibold text-gray-800 mb-4">Before and After Comparison</h2>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Original Image</h3>
                    <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
                      {image && (
                        <img
                          src={image.src}
                          alt="Original"
                          className="w-full h-auto"
                        />
                      )}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">
                      Processed ({colorBlocks.length} colors)
                    </h3>
                    <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
                      {processedImageUrl && (
                        <img
                          src={processedImageUrl}
                          alt="Processed"
                          className="w-full h-auto"
                        />
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-800">
                  Extracted Colors ({colorBlocks.length})
                </h2>
                <div className="flex gap-3">
                  <button
                    onClick={handleDownloadCSV}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    Download CSV
                  </button>
                  <button
                    onClick={handleDownloadSTL}
                    disabled={processing}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:bg-gray-400"
                  >
                    <Download className="w-4 h-4" />
                    {processing ? 'Generating...' : 'Download All STLs (ZIP)'}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {colorBlocks.map((color, index) => (
                  <div
                    key={index}
                    className="border rounded-lg p-3 hover:shadow-lg transition-shadow"
                  >
                    <div
                      className="w-full h-20 rounded-md mb-2"
                      style={{ backgroundColor: `rgb(${color.r},${color.g},${color.b})` }}
                    />
                    <div className="text-xs text-gray-600 mb-1">
                      RGB({color.r},{color.g},{color.b})
                    </div>
                    <div className="text-xs text-gray-500 mb-2">
                      {color.count} pixels
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {image && colorBlocks.length === 0 && !processing && (
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

export default ImageToMeshConverter;
