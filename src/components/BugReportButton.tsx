import { useTranslation } from '../i18n';
import { useState } from 'react';
import { Bug } from 'lucide-react';
import type { ConverterBugReportState } from '../api/types';
import { BugReportModal } from './BugReportModal';

export function BugReportButton({ context }: { context: ConverterBugReportState }) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  return <>
    <button
      type="button"
      className="fixed right-4 z-40 flex h-11 w-11 items-center justify-center rounded-full border border-ink bg-paper-raised text-ink shadow-lift transition-colors hover:bg-ink hover:text-paper-raised"
      style={{ bottom: 'calc(1.5rem + env(safe-area-inset-bottom, 0px))' }}
      aria-label={t('feedback:reportABug')}
      title={t('feedback:reportABug')}
      data-html2canvas-ignore
      onClick={() => setIsOpen(true)}
    >
      <Bug className="h-5 w-5" aria-hidden="true" />
    </button>
    {isOpen && <BugReportModal context={context} onClose={() => setIsOpen(false)} />}
  </>;
}
