import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
/**
 * Batch processing component for multiple image upload and conversion
 */
import React, { useState, useRef, useCallback } from 'react';
import { Upload, X, Download, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import type {
  BatchProcessResponse,
  FilamentColorConfig,
  FilamentPreset,
} from '../api/types';
import { batchProcessImages, batchDownloadSTL } from '../api/client';

const MAX_FILES = 20;
const VALID_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'];

interface BatchProcessorProps {
  maxColors: number;
  colorThreshold: number;
  pixelSize: number;
  layerHeight: number;
  layerCount: number;
  whiteBackingLayers: number;
  backingFilament?: string;
  filamentPreset?: FilamentPreset;
  filamentColors?: FilamentColorConfig[];
  detailSize: number;
}

export const BatchProcessor: React.FC<BatchProcessorProps> = ({
  maxColors,
  colorThreshold,
  pixelSize,
  layerHeight,
  layerCount,
  whiteBackingLayers,
  backingFilament,
  filamentPreset,
  filamentColors,
  detailSize,
}) => {
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
  const [files, setFiles] = useState<File[]>([]);
  const [processing, setProcessing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [results, setResults] = useState<BatchProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    setError(null);

    const validFiles = selected.filter(f => VALID_TYPES.includes(f.type));
    if (validFiles.length !== selected.length) {
      setError(`${selected.length - validFiles.length} file(s) skipped (unsupported format)`);
    }

    setFiles(prev => {
      const combined = [...prev, ...validFiles];
      if (combined.length > MAX_FILES) {
        setError(`Maximum ${MAX_FILES} images allowed. Extra files were dropped.`);
        return combined.slice(0, MAX_FILES);
      }
      // Clear results when new files are added to avoid stale index mapping
      setResults(null);
      return combined;
    });

    // Reset input so same files can be re-added
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setResults(null);
  }, []);

  const clearAll = useCallback(() => {
    setFiles([]);
    setResults(null);
    setError(null);
  }, []);

  const handleProcess = useCallback(async () => {
    if (files.length === 0) return;

    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setProcessing(true);
    setError(null);
    setResults(null);

    try {
      const result = await batchProcessImages(
        files,
        { maxColors, colorThreshold, pixelSize, detailSize },
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setResults(result);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to process batch');
      }
    } finally {
      if (!controller.signal.aborted) {
        setProcessing(false);
      }
    }
  }, [files, maxColors, colorThreshold, pixelSize, detailSize]);

  const handleDownloadSTL = useCallback(async () => {
    if (files.length === 0) return;

    // Abort any existing download
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setDownloading(true);
    setError(null);

    try {
      await batchDownloadSTL(files, {
        maxColors,
        colorThreshold,
        pixelSize,
        layerHeight,
        layerCount,
        whiteBackingLayers,
        backingFilament,
        filamentPreset: filamentPreset,
        filamentColors,
        detailSize,
      }, controller.signal);
    } catch (err) {
      // Don't show error if aborted
      if (controller.signal.aborted) return;
      setError(err instanceof Error ? err.message : 'Failed to download batch STL');
    } finally {
      if (!controller.signal.aborted) {
        setDownloading(false);
      }
    }
  }, [files, maxColors, colorThreshold, pixelSize, layerHeight, layerCount, whiteBackingLayers, backingFilament, filamentPreset, filamentColors, detailSize]);

  return (
    <div className="space-y-4">
      {/* File Upload Area */}
      <div className="rounded-sheet border-2 border-dashed border-rule-strong p-6 transition-colors hover:border-ink hover:bg-paper-sunk/60">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={processing || downloading}
          className="flex w-full flex-col items-center gap-2 text-ink disabled:opacity-50"
        >
          <Upload className="h-7 w-7" aria-hidden="true" />
          <span className="font-semibold">{t('batch:selectImages', { max: MAX_FILES })}</span>
          <span className="font-mono text-xs text-ink-muted">PNG, JPEG, GIF, WebP, BMP</span>
        </button>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="rounded-sheet border border-rule bg-paper p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-ink">
              {t('batch:selected', { count: files.length })}
            </h3>
            <button
              onClick={clearAll}
              disabled={processing || downloading}
              className="tv-link hover:!text-signal-error"
            >{t('batch:clearAll')}</button>
          </div>
          <div className="tv-scroll max-h-48 space-y-1 overflow-y-auto">
            {files.map((file, idx) => {
              const result = results?.results[idx];
              return (
                <div key={`${file.name}-${idx}`} className="flex items-center justify-between rounded-sheet border border-rule/70 bg-paper-raised px-3 py-1.5 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    {result && (
                      result.status === 'success'
                        ? <CheckCircle className="h-4 w-4 flex-shrink-0 text-signal-ok" aria-hidden="true" />
                        : <AlertCircle className="h-4 w-4 flex-shrink-0 text-signal-error" aria-hidden="true" />
                    )}
                    <span className="truncate">{file.name}</span>
                    <span className="flex-shrink-0 font-mono text-xs text-ink-muted">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  {result?.status === 'error' && (
                    <span className="mx-2 max-w-[200px] truncate text-xs text-signal-error" title={localize(result.error)}>
                      {localize(result.error)}
                    </span>
                  )}
                  <button
                    aria-label={t('common:removeFile', { name: file.name })}
                    onClick={() => removeFile(idx)}
                    disabled={processing || downloading}
                    className="flex-shrink-0 text-ink-muted hover:text-signal-error disabled:opacity-50"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div role="alert" className="rounded-sheet border border-signal-error/30 border-l-4 border-l-signal-error bg-signal-error/5 p-3 text-sm text-signal-error">
          {localize(error)}
        </div>
      )}

      {/* Results Summary */}
      {results && (
        <div role="status" className="rounded-sheet border border-signal-ok/30 border-l-4 border-l-signal-ok bg-signal-ok/5 p-4">
          <h3 className="mb-1 font-semibold text-signal-ok">{t('batch:batchProcessingComplete')}</h3>
          <p className="text-sm text-ink-soft">
            {t('batch:summary', { success: results.successCount, total: results.totalImages })}
            {results.errorCount > 0 && (
              <span className="text-signal-error">{' '}{t('batch:failed', { count: results.errorCount })}</span>
            )}
          </p>
        </div>
      )}

      {/* Action Buttons */}
      {files.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            onClick={handleProcess}
            disabled={processing || downloading || files.length === 0}
            className="tv-btn-outline flex-1 !py-2.5"
          >
            {processing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{t('common:processing')}</>
            ) : (
              t('batch:previewBatch')
            )}
          </button>
          <button
            onClick={handleDownloadSTL}
            disabled={processing || downloading || files.length === 0}
            className="tv-btn-primary flex-1 !py-2.5"
          >
            {downloading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{t('batch:generatingStls')}</>
            ) : (
              <>
                <Download className="h-4 w-4" aria-hidden="true" />{t('batch:downloadAllStls')}</>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
