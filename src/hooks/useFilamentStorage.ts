/**
 * Custom hook for persisting filament presets in localStorage
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
import type { FilamentColorConfig } from '../api/types';

const STORAGE_KEY = 'tinting-voxel_filament_presets';
const LAST_PRESET_KEY = 'tinting-voxel_last_preset';

export interface SavedPreset {
  id: string;
  name: string;
  colors: FilamentColorConfig[];
  createdAt: number;
  updatedAt: number;
}

interface FilamentStorage {
  presets: SavedPreset[];
  savePreset: (name: string, colors: FilamentColorConfig[]) => SavedPreset;
  updatePreset: (id: string, name: string, colors: FilamentColorConfig[]) => void;
  deletePreset: (id: string) => void;
  renamePreset: (id: string, name: string) => void;
  exportPresets: () => string;
  importPresets: (json: string) => { imported: number; errors: string[] };
  lastPresetId: string | null;
  setLastPresetId: (id: string | null) => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** Normalize a persisted/imported color to the current schema:
 * exactly name, hex, transmission_distance, and optional k. Fields removed
 * from the model (alpha, td_rgb, td_neutral, td_scale, td_gamma, k_rgb) are
 * stripped so outbound payloads never trip the backend's extra='forbid'. */
function normalizeColor(c: Record<string, unknown>): FilamentColorConfig {
  const out: FilamentColorConfig = {
    name: String(c.name),
    hex: String(c.hex),
    transmission_distance: Number(c.transmission_distance),
  };
  if (typeof c.k === 'number' && Number.isFinite(c.k)) out.k = c.k;
  return out;
}

function loadPresets(): SavedPreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isValidPreset).map((p) => ({
      ...p,
      colors: p.colors.map((c) => normalizeColor(c as unknown as Record<string, unknown>)),
    }));
  } catch {
    return [];
  }
}

function savePresetsToStorage(presets: SavedPreset[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    // localStorage quota exceeded or unavailable
  }
}

function isValidPreset(p: unknown): p is SavedPreset {
  if (typeof p !== 'object' || p === null) return false;
  const obj = p as Record<string, unknown>;
  if (typeof obj.id !== 'string') return false;
  if (typeof obj.name !== 'string') return false;
  if (!Array.isArray(obj.colors)) return false;
  if (obj.colors.length < 1) return false;
  for (const c of obj.colors) {
    if (typeof c !== 'object' || c === null) return false;
    const color = c as Record<string, unknown>;
    if (typeof color.name !== 'string') return false;
    if (typeof color.hex !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(color.hex)) return false;
    if (typeof color.transmission_distance !== 'number') return false;
  }
  return true;
}

export const useFilamentStorage = (): FilamentStorage => {
  const [presets, setPresets] = useState<SavedPreset[]>(loadPresets);
  const [lastPresetId, setLastPresetIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LAST_PRESET_KEY);
    } catch {
      return null;
    }
  });

  // Sync state to localStorage whenever presets change
  useEffect(() => {
    savePresetsToStorage(presets);
  }, [presets]);

  const setLastPresetId = useCallback((id: string | null) => {
    setLastPresetIdState(id);
    try {
      if (id) {
        localStorage.setItem(LAST_PRESET_KEY, id);
      } else {
        localStorage.removeItem(LAST_PRESET_KEY);
      }
    } catch {
      // localStorage unavailable
    }
  }, []);

  const savePreset = useCallback((name: string, colors: FilamentColorConfig[]): SavedPreset => {
    const now = Date.now();
    const preset: SavedPreset = {
      id: generateId(),
      name: name.trim(),
      colors: [...colors],
      createdAt: now,
      updatedAt: now,
    };
    setPresets(prev => [...prev, preset]);
    return preset;
  }, []);

  const updatePreset = useCallback((id: string, name: string, colors: FilamentColorConfig[]) => {
    setPresets(prev => prev.map(p =>
      p.id === id
        ? { ...p, name: name.trim(), colors: [...colors], updatedAt: Date.now() }
        : p
    ));
  }, []);

  const deletePreset = useCallback((id: string) => {
    setPresets(prev => prev.filter(p => p.id !== id));
    setLastPresetIdState(prev => prev === id ? null : prev);
    try {
      const current = localStorage.getItem(LAST_PRESET_KEY);
      if (current === id) localStorage.removeItem(LAST_PRESET_KEY);
    } catch {
      // localStorage unavailable
    }
  }, []);

  const renamePreset = useCallback((id: string, name: string) => {
    setPresets(prev => prev.map(p =>
      p.id === id
        ? { ...p, name: name.trim(), updatedAt: Date.now() }
        : p
    ));
  }, []);

  const exportPresets = useCallback((): string => {
    return JSON.stringify(presets, null, 2);
  }, [presets]);

  const importPresets = useCallback((json: string): { imported: number; errors: string[] } => {
    const errors: string[] = [];
    let imported = 0;

    try {
      const parsed = JSON.parse(json);
      if (!Array.isArray(parsed)) {
        return { imported: 0, errors: ['Invalid format: expected an array of presets'] };
      }

      const validPresets: SavedPreset[] = [];
      for (let i = 0; i < parsed.length; i++) {
        if (isValidPreset(parsed[i])) {
          validPresets.push({
            ...parsed[i],
            colors: (parsed[i].colors as Record<string, unknown>[]).map(normalizeColor),
            id: generateId(), // assign new IDs to avoid collisions
            createdAt: parsed[i].createdAt || Date.now(),
            updatedAt: Date.now(),
          });
          imported++;
        } else {
          errors.push(`Preset at index ${i} is invalid and was skipped`);
        }
      }

      if (validPresets.length > 0) {
        setPresets(prev => [...prev, ...validPresets]);
      }
    } catch {
      errors.push('Failed to parse JSON');
    }

    return { imported, errors };
  }, []);

  // Memoize the returned object to prevent unnecessary re-renders
  return useMemo(() => ({
    presets,
    savePreset,
    updatePreset,
    deletePreset,
    renamePreset,
    exportPresets,
    importPresets,
    lastPresetId,
    setLastPresetId,
  }), [presets, savePreset, updatePreset, deletePreset, renamePreset, exportPresets, importPresets, lastPresetId, setLastPresetId]);
};
