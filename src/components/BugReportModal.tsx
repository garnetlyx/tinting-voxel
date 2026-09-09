import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, Loader2, X } from 'lucide-react';
import type { ConverterBugReportState } from '../api/types';
import { submitBugReport } from '../api/client';
import { captureBugReportScreenshot, collectBugReportContext } from '../utils/bugReport';

export function BugReportModal({ context, onClose }: { context: ConverterBugReportState; onClose: () => void }) {
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
  const [description, setDescription] = useState('');
  const [includeScreenshot, setIncludeScreenshot] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [reportId, setReportId] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.querySelector<HTMLTextAreaElement>('textarea')?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!busyRef.current) closeRef.current();
      }
      if (event.key === 'Tab') {
        const elements = dialogRef.current?.querySelectorAll<HTMLElement>(':is(button, textarea, input):not(:disabled)');
        if (!elements?.length) { event.preventDefault(); return; }
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && (document.activeElement === first || !dialogRef.current?.contains(document.activeElement))) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !dialogRef.current?.contains(document.activeElement))) {
          event.preventDefault(); first.focus();
        }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => {
      abortRef.current?.abort();
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  useEffect(() => {
    if (reportId) dialogRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
  }, [reportId]);

  const submit = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setSubmitting(true);
    setError('');
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      let screenshot: string | undefined;
      if (includeScreenshot) {
        try { screenshot = await captureBugReportScreenshot(); }
        catch { throw new Error('Could not capture the page. Uncheck the screenshot option to send the report without it.'); }
      }
      if (controller.signal.aborted) return;
      const response = await submitBugReport({ description: description.trim(), frontendContext: collectBugReportContext(context), screenshot }, controller.signal);
      if (!controller.signal.aborted) setReportId(response.reportId);
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not send your report. Please try again.');
    } finally {
      busyRef.current = false;
      if (!controller.signal.aborted) setSubmitting(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" data-html2canvas-ignore
      onMouseDown={event => { if (event.target === event.currentTarget && !busyRef.current) onClose(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="bug-report-title" aria-describedby="bug-report-help"
        aria-busy={submitting} className="w-full max-w-lg max-h-[90dvh] overflow-y-auto rounded-2xl bg-white p-6 text-gray-800 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 id="bug-report-title" className="text-xl font-semibold">{t('feedback:reportABug')}</h2>
          <button type="button" aria-label={t('feedback:closeBugReport')} disabled={submitting} onClick={onClose} className="rounded-lg p-2 hover:bg-gray-100 disabled:opacity-50">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <p id="bug-report-help" className="mb-4 text-sm text-gray-500">{t('feedback:descriptionHelp')}</p>
        {reportId ? <div role="status" className="space-y-4">
          <p className="flex items-center gap-2 font-medium text-green-700"><CheckCircle2 className="h-5 w-5" />{t('feedback:thanksYourReportHasBeenReceived')}</p>
          <p className="break-all text-xs text-gray-500">{t('feedback:reportId')}{' '}{reportId}</p>
          <button type="button" onClick={onClose} className="w-full rounded-lg bg-purple-600 px-4 py-2 text-white hover:bg-purple-700">{t('common:done')}</button>
        </div> : <form onSubmit={event => { event.preventDefault(); void submit(); }}>
          <label htmlFor="bug-report-description" className="mb-1 block text-sm font-medium">{t('feedback:whatHappened')}<span className="font-normal text-gray-500">{t('feedback:optional')}</span></label>
          <textarea id="bug-report-description" value={description} onChange={event => setDescription(event.target.value.slice(0, 1000))}
            maxLength={1000} rows={4} disabled={submitting} aria-describedby="bug-report-count"
            placeholder={t('feedback:descriptionPlaceholder')}
            className="w-full resize-y rounded-lg border border-gray-300 p-3 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-60" />
          <p id="bug-report-count" className="mb-4 text-right text-xs text-gray-500">{description.length}/1000</p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={includeScreenshot} onChange={event => setIncludeScreenshot(event.target.checked)} disabled={submitting} />{t('feedback:includeAScreenshotOfTheCurrentView')}</label>
          <p className="mb-5 mt-1 text-xs text-gray-500">{t('feedback:screenshotHelp')}</p>
          {error && <p role="alert" className="mb-4 text-sm text-red-700">{localize(error)}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} disabled={submitting} className="flex-1 rounded-lg border border-gray-300 px-4 py-2 hover:bg-gray-50 disabled:opacity-50">{t('common:cancel')}</button>
            <button type="submit" disabled={submitting} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-white hover:bg-purple-700 disabled:opacity-50">
              {submitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}{submitting ? t('feedback:sending') : t('feedback:sendReport')}
            </button>
          </div>
        </form>}
      </div>
    </div>, document.body,
  );
}
