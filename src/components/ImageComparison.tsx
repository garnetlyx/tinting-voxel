import { useTranslation } from '../i18n';
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

const Figure: React.FC<{ letter: string; caption: string; children: React.ReactNode }> = ({ letter, caption, children }) => (
  <figure className="min-w-0">
    <div className="overflow-hidden rounded-sheet border border-rule bg-paper">{children}</div>
    <figcaption className="mt-2 flex items-baseline gap-2 text-sm">
      <span className="font-mono text-xs text-ink-muted" aria-hidden="true">{letter}</span>
      <span className="font-medium text-ink-soft">{caption}</span>
    </figcaption>
  </figure>
);

export const ImageComparison: React.FC<ImageComparisonProps> = ({
  originalImage,
  intermediateImageUrl = null,
  intermediateLabel,
  processedImageUrl,
  colorCount,
  processedLabel,
}) => {
  const { t } = useTranslation();
  const showIntermediate = Boolean(intermediateImageUrl);
  const gridClassName = showIntermediate ? 'grid gap-5 md:grid-cols-3' : 'grid gap-5 md:grid-cols-2';

  return (
    <section>
      <h2 className="tv-heading mb-4 text-xl">{t('preview:beforeAndAfterComparison')}</h2>
      <div className={gridClassName}>
        <Figure letter="A" caption={t('preview:originalImage')}>
          {originalImage && (
            <img src={originalImage.src} alt={t('preview:original')} className="h-auto w-full" />
          )}
        </Figure>
        {showIntermediate && (
          <Figure
            letter="B"
            caption={t('preview:comparisonLabel', { label: intermediateLabel ?? t('preview:intermediate'), count: colorCount })}
          >
            <img
              src={intermediateImageUrl ?? undefined}
              alt={intermediateLabel ?? t('preview:intermediate')}
              className="h-auto w-full"
            />
          </Figure>
        )}
        <Figure
          letter={showIntermediate ? 'C' : 'B'}
          caption={t('preview:comparisonLabel', { label: processedLabel ?? t('preview:processed'), count: colorCount })}
        >
          {processedImageUrl && (
            <img src={processedImageUrl} alt={t('preview:processed')} className="h-auto w-full" />
          )}
        </Figure>
      </div>
    </section>
  );
};
