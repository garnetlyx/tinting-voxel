/**
 * Before/After image comparison component
 */
import React from 'react';

interface ImageComparisonProps {
  originalImage: HTMLImageElement | null;
  processedImageUrl: string | null;
  colorCount: number;
}

export const ImageComparison: React.FC<ImageComparisonProps> = ({
  originalImage,
  processedImageUrl,
  colorCount,
}) => {
  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Before and After Comparison</h2>
      <div className="grid md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Original Image</h3>
          <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
            {originalImage && (
              <img
                src={originalImage.src}
                alt="Original"
                className="w-full h-auto"
              />
            )}
          </div>
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            Processed ({colorCount} colors)
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
  );
};
