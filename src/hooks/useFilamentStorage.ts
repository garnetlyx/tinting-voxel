/**
 * Custom hook for persisting filament presets in localStorage
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
import type { FilamentColorConfig } from '../api/types';
import { isFilamentColorConfig } from '../utils/filaments';

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

function loadPresets(): SavedPreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isValidPreset);
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
  return typeof obj.id === 'string' && typeof obj.name === 'string'
    && Array.isArray(obj.colors) && obj.colors.length > 0
    && obj.colors.every(isFilamentColorConfig);
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
      colors: structuredClone(colors),
      createdAt: now,
      updatedAt: now,
    };
    setPresets(prev => [...prev, preset]);
    return preset;
  }, []);

  const updatePreset = useCallback((id: string, name: string, colors: FilamentColorConfig[]) => {
    setPresets(prev => prev.map(p =>
      p.id === id
        ? { ...p, name: name.trim(), colors: structuredClone(colors), updatedAt: Date.now() }
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
            colors: parsed[i].colors,
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
