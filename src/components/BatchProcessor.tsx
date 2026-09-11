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
  }, [files, maxColors, colorThreshold, pixelSize, layerHeight, layerCount, whiteBackingLayers, filamentPreset, filamentColors, detailSize]);

  return (
    <div className="space-y-4">
      {/* File Upload Area */}
      <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 hover:border-purple-400 hover:bg-purple-50 transition-all">
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
          className="w-full flex flex-col items-center gap-2 text-gray-600 hover:text-purple-600 disabled:opacity-50"
        >
          <Upload className="w-8 h-8" />
          <span className="font-medium">{t('batch:selectImages', { max: MAX_FILES })}</span>
          <span className="text-sm text-gray-400">PNG, JPEG, GIF, WebP, BMP</span>
        </button>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-700">
              {t('batch:selected', { count: files.length })}
            </h3>
            <button
              onClick={clearAll}
              disabled={processing || downloading}
              className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50"
            >{t('batch:clearAll')}</button>
          </div>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {files.map((file, idx) => {
              const result = results?.results[idx];
              return (
                <div key={`${file.name}-${idx}`} className="flex items-center justify-between px-3 py-1.5 bg-white rounded text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    {result && (
                      result.status === 'success'
                        ? <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                        : <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    )}
                    <span className="truncate">{file.name}</span>
                    <span className="text-gray-400 flex-shrink-0">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  {result?.status === 'error' && (
                    <span className="text-red-500 text-xs truncate mx-2 max-w-[200px]" title={localize(result.error)}>
                      {localize(result.error)}
                    </span>
                  )}
                  <button
                    aria-label={t('common:removeFile', { name: file.name })}
                    onClick={() => removeFile(idx)}
                    disabled={processing || downloading}
                    className="text-gray-400 hover:text-red-500 disabled:opacity-50 flex-shrink-0"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {localize(error)}
        </div>
      )}

      {/* Results Summary */}
      {results && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h3 className="font-medium text-green-800 mb-1">{t('batch:batchProcessingComplete')}</h3>
          <p className="text-sm text-green-700">
            {t('batch:summary', { success: results.successCount, total: results.totalImages })}
            {results.errorCount > 0 && (
              <span className="text-red-600">{' '}{t('batch:failed', { count: results.errorCount })}</span>
            )}
          </p>
        </div>
      )}

      {/* Action Buttons */}
      {files.length > 0 && (
        <div className="flex gap-3">
          <button
            onClick={handleProcess}
            disabled={processing || downloading || files.length === 0}
            className="flex-1 py-2.5 px-4 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
          >
            {processing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />{t('common:processing')}</>
            ) : (
              t('batch:previewBatch')
            )}
          </button>
          <button
            onClick={handleDownloadSTL}
            disabled={processing || downloading || files.length === 0}
            className="flex-1 py-2.5 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
          >
            {downloading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />{t('batch:generatingStls')}</>
            ) : (
              <>
                <Download className="w-4 h-4" />{t('batch:downloadAllStls')}</>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
