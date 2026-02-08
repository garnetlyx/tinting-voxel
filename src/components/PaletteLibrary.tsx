/**
 * Palette library browser component.
 * Displays curated color palettes organized by category with color swatches.
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
  const [library, setLibrary] = useState<PaletteLibraryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
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
        const data = await getPaletteLibrary(selectedCategory ?? undefined, controller.signal);
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
  }, [isExpanded, selectedCategory]);

  const handleApply = useCallback((palette: PaletteInfo) => {
    const colors: FilamentColorConfig[] = palette.colors.map(c => ({
      name: c.name,
      hex: c.hex,
      transmission_distance: c.transmission_distance,
    }));
    onApplyPalette(colors);
  }, [onApplyPalette]);

  const categoryNames: Record<string, string> = library?.categories ?? {};

  return (
    <div className="border border-gray-200 rounded-lg">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2.5 text-left text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg flex items-center justify-between"
      >
        <span>Palette Library</span>
        <span className="text-gray-400 text-xs">
          {isExpanded ? 'Hide' : 'Browse curated palettes'}
        </span>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Category Filter */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                selectedCategory === null
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            {Object.keys(categoryNames).map((key) => (
              <button
                key={key}
                onClick={() => setSelectedCategory(key)}
                className={`px-3 py-1 text-xs rounded-full transition-colors capitalize ${
                  selectedCategory === key
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {key}
              </button>
            ))}
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-red-500 text-sm">{error}</p>
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
                    <h4 className="text-sm font-medium text-gray-800">{palette.name}</h4>
                    <span className="text-xs text-gray-400 capitalize">{palette.category}</span>
                  </div>
                  <p className="text-xs text-gray-500 mb-2">{palette.description}</p>

                  {/* Color Swatches */}
                  <div className="flex gap-1 mb-2">
                    {palette.colors.map((color, idx) => (
                      <div
                        key={idx}
                        className="flex flex-col items-center"
                        title={`${color.name} (${color.hex})`}
                      >
                        <div
                          className="w-6 h-6 rounded border border-gray-300"
                          style={{ backgroundColor: color.hex }}
                        />
                        <span className="text-[10px] text-gray-400 mt-0.5 truncate max-w-[40px]">
                          {color.name}
                        </span>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={() => handleApply(palette)}
                    disabled={disabled}
                    className="w-full py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 disabled:opacity-50 transition-colors"
                  >
                    Apply
                  </button>
                </div>
              ))}
            </div>
          )}

          {!loading && library && library.palettes.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-3">No palettes found</p>
          )}
        </div>
      )}
    </div>
  );
};
