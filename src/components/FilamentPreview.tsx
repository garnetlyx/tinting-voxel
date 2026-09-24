import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
/**
 * Filament preview component showing achievable color matrix from current configuration
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import type { BackingMode, FilamentColorConfig, FilamentPreset } from '../api/types';
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
  whiteBackingLayers: number;
  backingMode: BackingMode;
  isConfigValid: boolean;
  disabled?: boolean;
}

export const FilamentPreview: React.FC<FilamentPreviewProps> = ({
  filamentColors,
  filamentPreset,
  layerCount,
  layerHeight,
  whiteBackingLayers,
  backingMode,
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
        ? { filamentPreset, layerCount, layerHeight, whiteBackingLayers, backingMode }
        : { filamentColors, layerCount, layerHeight, whiteBackingLayers, backingMode };
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
  }, [filamentColors, filamentPreset, layerCount, layerHeight, whiteBackingLayers, backingMode, isConfigValid, disabled]);

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
        <h3 className="text-sm font-semibold text-ink">{t('filaments:achievableFilamentGamut')}</h3>
        <button
          type="button"
          onClick={fetchPreview}
          disabled={loading || disabled}
          className="tv-link"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />{t('common:refresh')}</button>
      </div>

      {loading && !preview && (
        <div className="flex items-center justify-center py-6 text-sm text-ink-muted">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />{t('filaments:generatingPreview')}</div>
      )}

      {error && (
        <div className="rounded-sheet bg-signal-error/5 p-2 text-xs text-signal-error">
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
              className={`w-full rounded-sheet border border-rule ${loading ? 'opacity-50' : ''}`}
              style={{ imageRendering: 'pixelated' }}
            />
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <RefreshCw className="h-5 w-5 animate-spin text-ink" aria-hidden="true" />
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-ink-muted">
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
                  className="flex items-start gap-1.5 rounded-sheet bg-signal-warn/10 p-2 text-xs text-signal-warn"
                >
                  <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0" aria-hidden="true" />
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
