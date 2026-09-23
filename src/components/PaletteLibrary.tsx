import { usePaletteText } from '../i18n/catalog';
import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
/**
 * Palette library browser component.
 * Displays the supported filament configurations with color swatches.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import type { PaletteInfo, PaletteLibraryResponse, FilamentColorConfig } from '../api/types';
import { getPaletteLibrary } from '../api/client';

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
    <div className="border border-gray-200 rounded-lg">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2.5 text-left text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg flex items-center justify-between"
      >
        <span>{t('palettes:paletteLibrary')}</span>
        <span className="text-gray-400 text-xs">
          {isExpanded ? t('common:hide') : t('palettes:browseCuratedPalettes')}
        </span>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-red-500 text-sm">{localize(error)}</p>
          )}

          {/* Palette Grid */}
          {!loading && library && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-80 overflow-y-auto">
              {library.palettes.map(palette => (
                <div
                  key={palette.id}
                  className="border border-gray-200 rounded-lg p-3 hover:border-purple-300 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <h4 className="text-sm font-medium text-gray-800">{paletteText(`${palette.id}_name`, palette.name)}</h4>
                  </div>

                  {/* Color Swatches */}
                  <div className="flex gap-1 mb-2">
                    {palette.colors.map((color, idx) => (
                      <div
                        key={idx}
                        className="flex flex-col items-center"
                        title={t('common:colorEntry', { index: idx + 1, code: color.name[0]?.toUpperCase() ?? '?', hex: color.hex })}
                      >
                        <div
                          className="w-6 h-6 rounded border border-gray-300"
                          style={{ backgroundColor: color.hex }}
                        />
                        <span className="text-[10px] text-gray-400 mt-0.5 truncate max-w-[40px]">
                          {color.name[0]?.toUpperCase() ?? String(idx + 1)}
                        </span>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={() => handleApply(palette)}
                    disabled={disabled}
                    className="w-full py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 disabled:opacity-50 transition-colors"
                  >{t('common:apply')}</button>
                </div>
              ))}
            </div>
          )}

          {!loading && library && library.palettes.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-3">{t('palettes:noPalettesFound')}</p>
          )}
        </div>
      )}
    </div>
  );
};
