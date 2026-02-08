/**
 * Loading spinner with optional progress stage display
 */
import React from 'react';

export type ProcessingStage =
  | 'uploading'
  | 'processing'
  | 'generating'
  | 'idle';

const STAGE_LABELS: Record<ProcessingStage, string> = {
  uploading: 'Uploading image...',
  processing: 'Processing colors...',
  generating: 'Generating STL files...',
  idle: 'Processing...',
};

const STAGE_ORDER: ProcessingStage[] = ['uploading', 'processing', 'generating'];

interface LoadingSpinnerProps {
  message?: string;
  stage?: ProcessingStage;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message,
  stage = 'idle',
}) => {
  const displayMessage = message || STAGE_LABELS[stage] || 'Processing...';
  const currentIdx = STAGE_ORDER.indexOf(stage);
  const showStages = stage !== 'idle' && currentIdx >= 0;

  return (
    <div className="text-center py-8">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mx-auto mb-4"></div>
      <p className="text-gray-700 font-medium mb-3">{displayMessage}</p>
      {showStages && (
        <div className="flex justify-center gap-6 text-sm">
          {STAGE_ORDER.map((s, idx) => {
            const isComplete = idx < currentIdx;
            const isCurrent = idx === currentIdx;
            return (
              <div
                key={s}
                className={`flex items-center gap-1.5 ${
                  isCurrent
                    ? 'text-purple-600 font-medium'
                    : isComplete
                    ? 'text-green-600'
                    : 'text-gray-400'
                }`}
              >
                <span className="text-xs">
                  {isComplete ? '\u2713' : isCurrent ? '\u25CF' : '\u25CB'}
                </span>
                {STAGE_LABELS[s].replace('...', '')}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
