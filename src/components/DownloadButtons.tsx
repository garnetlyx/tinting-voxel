import { useTranslation } from '../i18n';
/**
 * Download buttons component (CSV, STL, 3MF, and Print Settings)
 */
import React, { useId } from 'react';
import { Download, FileSpreadsheet, Settings } from 'lucide-react';

interface DownloadButtonsProps {
  onDownloadCSV: () => void;
  onDownloadSTL: () => void;
  onDownload3MF?: () => void;
  onDownloadPrintSettings?: () => void;
  processing: boolean;
  showCSV?: boolean;
  /** Model size and height, shown under the heading. */
  summary?: string;
}

const MODEL_BUTTON = 'inline-flex items-center justify-center gap-2 rounded-sheet border border-paper-raised bg-paper-raised px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-yellow hover:border-yellow disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-paper-raised disabled:hover:border-paper-raised';
const EXTRA_BUTTON = 'inline-flex items-center justify-center gap-2 rounded-sheet border border-paper-raised/40 px-3 py-2 text-sm font-medium text-paper-raised transition-colors hover:border-paper-raised hover:bg-paper-raised/10 disabled:cursor-not-allowed disabled:opacity-50';

export const DownloadButtons: React.FC<DownloadButtonsProps> = ({
  onDownloadCSV,
  onDownloadSTL,
  onDownload3MF,
  onDownloadPrintSettings,
  processing,
  showCSV = true,
  summary,
}) => {
  const { t } = useTranslation();
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-4 rounded-sheet bg-ink p-4 text-paper-raised sm:p-5 lg:flex-row lg:items-center lg:justify-between"
    >
      <div className="min-w-0">
        <h2 id={headingId} className="tv-heading !text-paper-raised">{t('converter:exportTitle')}</h2>
        {summary && <p className="mt-0.5 font-mono text-xs text-paper-raised/70">{summary}</p>}
      </div>
      <div className="flex flex-wrap gap-2 lg:justify-end">
        <button type="button" onClick={onDownloadSTL} disabled={processing} className={MODEL_BUTTON}>
          <Download className="h-4 w-4" aria-hidden="true" />
          {processing ? t('common:generating') : t('converter:downloadStlZip')}
        </button>
        {onDownload3MF && (
          <button type="button" onClick={onDownload3MF} disabled={processing} className={MODEL_BUTTON}>
            <Download className="h-4 w-4" aria-hidden="true" />
            {processing ? t('common:generating') : t('converter:download3mf')}
          </button>
        )}
        {showCSV && (
          <button type="button" onClick={onDownloadCSV} disabled={processing} className={EXTRA_BUTTON}>
            <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />{t('converter:downloadCsv')}
          </button>
        )}
        {onDownloadPrintSettings && (
          <button type="button" onClick={onDownloadPrintSettings} disabled={processing} className={EXTRA_BUTTON}>
            <Settings className="h-4 w-4" aria-hidden="true" />{t('converter:printSettings')}
          </button>
        )}
      </div>
    </section>
  );
};
