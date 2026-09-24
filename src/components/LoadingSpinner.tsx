/**
 * Loading spinner with optional progress stage display
 */
import { useTranslation } from '../i18n';
import React from 'react';
import { OverprintMark } from './OverprintMark';

export type ProcessingStage =
  | 'uploading'
  | 'processing'
  | 'generating'
  | 'idle';

const STAGE_LABELS = {
  uploading: 'converter:uploading',
  processing: 'converter:processingColors',
  generating: 'converter:generatingStl',
  idle: 'common:processing',
} as const;

const STAGE_ORDER: ProcessingStage[] = ['uploading', 'processing', 'generating'];

interface LoadingSpinnerProps {
  message?: string;
  stage?: ProcessingStage;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message,
  stage = 'idle',
}) => {
  const { t } = useTranslation();
  const displayMessage = message || t(STAGE_LABELS[stage]);
  const currentIdx = STAGE_ORDER.indexOf(stage);
  const showStages = stage !== 'idle' && currentIdx >= 0;

  return (
    <div role="status" className="flex flex-col items-center py-12 text-center">
      <div className="animate-spin [animation-duration:2.6s]">
        <OverprintMark className="h-16 w-16" animated={false} />
      </div>
      <p className="mt-5 font-semibold text-ink">{displayMessage}</p>
      {showStages && (
        <ol className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm">
          {STAGE_ORDER.map((s, idx) => {
            const isComplete = idx < currentIdx;
            const isCurrent = idx === currentIdx;
            return (
              <li
                key={s}
                aria-current={isCurrent ? 'step' : undefined}
                className={`flex items-center gap-2 ${
                  isCurrent ? 'font-semibold text-ink' : isComplete ? 'text-signal-ok' : 'text-ink-muted'
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`flex h-5 w-5 items-center justify-center rounded-full border font-mono text-[10px] ${
                    isCurrent ? 'border-ink bg-ink text-paper-raised' : isComplete ? 'border-signal-ok' : 'border-rule-strong'
                  }`}
                >
                  {isComplete ? '✓' : idx + 1}
                </span>
                {t(STAGE_LABELS[s]).replace(/(?:\.\.\.|…)$/, '')}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
};
