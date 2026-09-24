import { usePaletteText } from '../i18n/catalog';
import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
/**
 * Palette library browser component.
 * Displays the supported filament configurations with color swatches.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { ChevronDown, Loader2 } from 'lucide-react';
import type { PaletteInfo, PaletteLibraryResponse, FilamentColorConfig } from '../api/types';
import { getPaletteLibrary } from '../api/client';
import { filamentLabel } from '../utils/filaments';

interface PaletteLibraryProps {
  onApplyPalette: (colors: FilamentColorConfig[]) => void;
  disabled?: boolean;
}

export const PaletteLibrary: React.FC<PaletteLibraryProps> = ({
  onApplyPalette,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
  const paletteText = usePaletteText();
  const [library, setLibrary] = useState<PaletteLibraryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const abortRef = React.useRef<AbortController | null>(null);

  useEffect(() => {
    const loadLibrary = async () => {
      // Abort any existing request
      if (abortRef.current) {
        abortRef.current.abort();
      }
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      setError(null);
      try {
        const data = await getPaletteLibrary(controller.signal);
        setLibrary(data);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : 'Failed to load palettes');
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    if (isExpanded) {
      loadLibrary();
    }

    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, [isExpanded]);

  const handleApply = useCallback((palette: PaletteInfo) => {
    const colors = structuredClone(palette.colors);
    onApplyPalette(colors);
  }, [onApplyPalette]);


  return (
    <div className="rounded-sheet border border-rule bg-paper-raised">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        className="flex w-full items-center justify-between gap-3 rounded-sheet px-4 py-2.5 text-left text-sm font-semibold text-ink transition-colors hover:bg-paper-sunk"
      >
        <span>{t('palettes:paletteLibrary')}</span>
        <span className="flex items-center gap-1 text-xs font-normal text-ink-muted">
          {isExpanded ? t('common:hide') : t('palettes:browseCuratedPalettes')}
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} aria-hidden="true" />
        </span>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-ink" aria-hidden="true" />
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-sm text-signal-error">{localize(error)}</p>
          )}

          {/* Palette Grid */}
          {!loading && library && (
            <div className="tv-scroll grid max-h-80 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
              {library.palettes.map(palette => (
                <div
                  key={palette.id}
                  className="rounded-sheet border border-rule bg-paper p-3 transition-colors hover:border-ink"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-ink">{paletteText(`${palette.id}_name`, palette.name)}</h4>
                  </div>

                  {/* Color Swatches */}
                  <div className="mb-2.5 flex gap-1">
                    {palette.colors.map((color, idx) => (
                      <div
                        key={idx}
                        className="flex flex-col items-center"
                        title={t('common:colorEntry', { index: idx + 1, code: filamentLabel(color) || '?', hex: color.hex })}
                      >
                        <div
                          className="h-6 w-6 border border-ink/40"
                          style={{ backgroundColor: color.hex }}
                        />
                        <span className="mt-0.5 max-w-[40px] truncate font-mono text-[10px] text-ink-muted">
                          {filamentLabel(color) || String(idx + 1)}
                        </span>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={() => handleApply(palette)}
                    disabled={disabled}
                    className="tv-btn-outline tv-btn-sm w-full"
                  >{t('common:apply')}</button>
                </div>
              ))}
            </div>
          )}

          {!loading && library && library.palettes.length === 0 && (
            <p className="py-3 text-center text-sm text-ink-muted">{t('palettes:noPalettesFound')}</p>
          )}
        </div>
      )}
    </div>
  );
};
