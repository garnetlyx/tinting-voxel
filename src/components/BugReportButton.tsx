import { useState } from 'react';
import { Bug } from 'lucide-react';
import type { ConverterBugReportState } from '../api/types';
import { BugReportModal } from './BugReportModal';

export function BugReportButton({ context }: { context: ConverterBugReportState }) {
  const [isOpen, setIsOpen] = useState(false);
  return <>
    <button
      type="button"
      className="fixed right-4 z-40 flex h-11 w-11 items-center justify-center rounded-full border border-purple-200 bg-white text-purple-700 shadow-lg hover:bg-purple-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-600"
      style={{ bottom: 'calc(1.5rem + env(safe-area-inset-bottom, 0px))' }}
      aria-label="Report a bug"
      title="Report a bug"
      data-html2canvas-ignore
      onClick={() => setIsOpen(true)}
    >
      <Bug className="h-5 w-5" aria-hidden="true" />
    </button>
    {isOpen && <BugReportModal context={context} onClose={() => setIsOpen(false)} />}
  </>;
}
