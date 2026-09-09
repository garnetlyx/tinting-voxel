import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
/**
 * Filament preview component showing achievable color matrix from current configuration
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import type { FilamentColorConfig, FilamentPreset } from '../api/types';
import { getFilamentPreview } from '../api/client';

interface ColorMatrixEntry {
  code: string;
  rgb: number[];
}

interface PreviewData {
  image: string;
  colorMatrix: ColorMatrixEntry[];
  stats: { colorCount: number; combinationCount: number };
  imageDimensions: { width: number; height: number };
  warnings: string[];
}

interface FilamentPreviewProps {
  filamentColors: FilamentColorConfig[];
  filamentPreset: FilamentPreset | null;
  layerCount: number;
  layerHeight: number;
  isConfigValid: boolean;
  disabled?: boolean;
}

export const FilamentPreview: React.FC<FilamentPreviewProps> = ({
  filamentColors,
  filamentPreset,
  layerCount,
  layerHeight,
  isConfigValid,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchPreview = useCallback(async () => {
    if (!isConfigValid || disabled) return;

    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      // Send only filamentPreset if it's set, otherwise send filamentColors
      const requestBody = filamentPreset
        ? { filamentPreset, layerCount, layerHeight }
        : { filamentColors, layerCount, layerHeight };
      const result = await getFilamentPreview(requestBody, controller.signal);
      if (!controller.signal.aborted) {
        setPreview(result);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to load preview');
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [filamentColors, filamentPreset, layerCount, layerHeight, isConfigValid, disabled]);

  // Auto-fetch on config change with debounce
  useEffect(() => {
    if (!isConfigValid) {
      setPreview(null);
      return;
    }

    const timer = setTimeout(fetchPreview, 500);
    return () => {
      clearTimeout(timer);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchPreview, isConfigValid]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  if (!isConfigValid) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-700">{t('filaments:achievableFilamentGamut')}</h4>
          <p className="text-xs text-gray-500">{t('filaments:gamutHelp')}</p>
        </div>
        <button
          onClick={fetchPreview}
          disabled={loading || disabled}
          className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-800 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />{t('common:refresh')}</button>
      </div>

      {loading && !preview && (
        <div className="flex items-center justify-center py-6 text-gray-400 text-sm">
          <RefreshCw className="w-4 h-4 animate-spin mr-2" />{t('filaments:generatingPreview')}</div>
      )}

      {error && (
        <div className="text-xs text-red-500 bg-red-50 p-2 rounded">
          {localize(error)}
        </div>
      )}

      {preview && (
        <div className="space-y-3">
          {/* Color matrix image */}
          <div className="relative">
            <img
              src={`data:image/png;base64,${preview.image}`}
              alt={t('filaments:filamentColorMatrixPreview')}
              className={`w-full rounded border border-gray-200 ${loading ? 'opacity-50' : ''}`}
              style={{ imageRendering: 'pixelated' }}
            />
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <RefreshCw className="w-5 h-5 animate-spin text-purple-600" />
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="flex gap-4 text-xs text-gray-500">
            <span>
              {t('filaments:filamentCount', { count: preview.stats.colorCount })}
            </span>
            <span>
              {t('filaments:combinations', { count: preview.stats.combinationCount })}
            </span>
            <span>
              {preview.imageDimensions.width}&times;{preview.imageDimensions.height}px
            </span>
          </div>

          {/* Warnings */}
          {preview.warnings.length > 0 && (
            <div className="space-y-1">
              {preview.warnings.map((warning, i) => (
                <div
                  key={i}
                  className="flex items-start gap-1.5 text-xs text-amber-700 bg-amber-50 p-2 rounded"
                >
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>{localize(warning)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
