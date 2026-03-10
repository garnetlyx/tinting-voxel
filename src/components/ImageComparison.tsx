/**
 * Before/After image comparison component
 */
import React from 'react';

interface ImageComparisonProps {
  originalImage: HTMLImageElement | null;
  intermediateImageUrl?: string | null;
  intermediateLabel?: string;
  processedImageUrl: string | null;
  colorCount: number;
  processedLabel?: string;
}

export const ImageComparison: React.FC<ImageComparisonProps> = ({
  originalImage,
  intermediateImageUrl = null,
  intermediateLabel = 'Intermediate',
  processedImageUrl,
  colorCount,
  processedLabel = 'Processed',
}) => {
  const showIntermediate = Boolean(intermediateImageUrl);
  const gridClassName = showIntermediate ? 'grid md:grid-cols-3 gap-6' : 'grid md:grid-cols-2 gap-6';

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Before and After Comparison</h2>
      <div className={gridClassName}>
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
        {showIntermediate && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              {intermediateLabel} ({colorCount} colors)
            </h3>
            <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
              <img
                src={intermediateImageUrl ?? undefined}
                alt={intermediateLabel}
                className="w-full h-auto"
              />
            </div>
          </div>
        )}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            {processedLabel} ({colorCount} colors)
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
