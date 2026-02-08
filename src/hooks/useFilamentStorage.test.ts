import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFilamentStorage } from './useFilamentStorage';
import type { FilamentColorConfig } from '../api/types';

const STORAGE_KEY = 'img2stl_filament_presets';
const LAST_PRESET_KEY = 'img2stl_last_preset';

const sampleColors: FilamentColorConfig[] = [
  { name: 'Cyan', hex: '#0086D6', transmission_distance: 3.0 },
  { name: 'Magenta', hex: '#EC008C', transmission_distance: 1.9 },
];

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('useFilamentStorage', () => {
  it('starts with empty presets when localStorage is empty', () => {
    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toEqual([]);
    expect(result.current.lastPresetId).toBeNull();
  });

  it('saves a preset and persists to localStorage', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let saved: ReturnType<typeof result.current.savePreset>;
    act(() => {
      saved = result.current.savePreset('My Preset', sampleColors);
    });

    expect(result.current.presets).toHaveLength(1);
    expect(result.current.presets[0].name).toBe('My Preset');
    expect(result.current.presets[0].colors).toEqual(sampleColors);
    expect(saved!.id).toBeTruthy();
  });

  it('trims whitespace from preset names on save', () => {
    const { result } = renderHook(() => useFilamentStorage());

    act(() => {
      result.current.savePreset('  My Preset  ', sampleColors);
    });

    expect(result.current.presets[0].name).toBe('My Preset');
  });

  it('updates a preset by id', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let id = '';
    act(() => {
      const saved = result.current.savePreset('Original', sampleColors);
      id = saved.id;
    });

    const newColors: FilamentColorConfig[] = [
      { name: 'Red', hex: '#FF0000', transmission_distance: 2.0 },
    ];

    act(() => {
      result.current.updatePreset(id, 'Updated', newColors);
    });

    expect(result.current.presets[0].name).toBe('Updated');
    expect(result.current.presets[0].colors).toEqual(newColors);
  });

  it('deletes a preset by id', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let id = '';
    act(() => {
      const saved = result.current.savePreset('To Delete', sampleColors);
      id = saved.id;
    });

    expect(result.current.presets).toHaveLength(1);

    act(() => {
      result.current.deletePreset(id);
    });

    expect(result.current.presets).toHaveLength(0);
  });

  it('clears lastPresetId when deleting the last-used preset', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let id = '';
    act(() => {
      const saved = result.current.savePreset('Active', sampleColors);
      id = saved.id;
    });

    act(() => {
      result.current.setLastPresetId(id);
    });

    expect(result.current.lastPresetId).toBe(id);

    act(() => {
      result.current.deletePreset(id);
    });

    expect(result.current.lastPresetId).toBeNull();
  });

  it('renames a preset', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let id = '';
    act(() => {
      const saved = result.current.savePreset('Old Name', sampleColors);
      id = saved.id;
    });

    act(() => {
      result.current.renamePreset(id, '  New Name  ');
    });

    expect(result.current.presets[0].name).toBe('New Name');
  });

  it('exports presets as JSON', () => {
    const { result } = renderHook(() => useFilamentStorage());

    act(() => {
      result.current.savePreset('Export Test', sampleColors);
    });

    const json = result.current.exportPresets();
    const parsed = JSON.parse(json);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].name).toBe('Export Test');
  });

  it('imports valid presets from JSON', () => {
    const { result } = renderHook(() => useFilamentStorage());

    const json = JSON.stringify([
      {
        id: 'old-id',
        name: 'Imported',
        colors: sampleColors,
        createdAt: 1000,
        updatedAt: 1000,
      },
    ]);

    let importResult: { imported: number; errors: string[] };
    act(() => {
      importResult = result.current.importPresets(json);
    });

    expect(importResult!.imported).toBe(1);
    expect(importResult!.errors).toHaveLength(0);
    expect(result.current.presets).toHaveLength(1);
    expect(result.current.presets[0].name).toBe('Imported');
    // Should get a new ID, not the old one
    expect(result.current.presets[0].id).not.toBe('old-id');
  });

  it('rejects invalid presets during import', () => {
    const { result } = renderHook(() => useFilamentStorage());

    const json = JSON.stringify([
      { id: 'x', name: 'Good', colors: sampleColors, createdAt: 1, updatedAt: 1 },
      { id: 'y', name: 'Bad', colors: [] }, // empty colors = invalid
      'not-an-object',
    ]);

    let importResult: { imported: number; errors: string[] };
    act(() => {
      importResult = result.current.importPresets(json);
    });

    expect(importResult!.imported).toBe(1);
    expect(importResult!.errors).toHaveLength(2);
  });

  it('handles invalid JSON in importPresets', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let importResult: { imported: number; errors: string[] };
    act(() => {
      importResult = result.current.importPresets('not valid json');
    });

    expect(importResult!.imported).toBe(0);
    expect(importResult!.errors).toContain('Failed to parse JSON');
  });

  it('returns error for non-array JSON in importPresets', () => {
    const { result } = renderHook(() => useFilamentStorage());

    let importResult: { imported: number; errors: string[] };
    act(() => {
      importResult = result.current.importPresets('{"not": "array"}');
    });

    expect(importResult!.imported).toBe(0);
    expect(importResult!.errors[0]).toContain('expected an array');
  });

  it('loads presets from localStorage on mount', () => {
    const preset = {
      id: 'test-123',
      name: 'Persisted',
      colors: sampleColors,
      createdAt: 1000,
      updatedAt: 1000,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify([preset]));

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toHaveLength(1);
    expect(result.current.presets[0].name).toBe('Persisted');
  });

  it('loads lastPresetId from localStorage on mount', () => {
    localStorage.setItem(LAST_PRESET_KEY, 'saved-id');

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.lastPresetId).toBe('saved-id');
  });

  it('handles corrupted localStorage data gracefully', () => {
    localStorage.setItem(STORAGE_KEY, 'not valid json');

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toEqual([]);
  });

  it('handles non-array localStorage data gracefully', () => {
    localStorage.setItem(STORAGE_KEY, '"just a string"');

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toEqual([]);
  });

  it('filters out invalid presets from localStorage', () => {
    const data = [
      { id: 'valid', name: 'Good', colors: sampleColors, createdAt: 1, updatedAt: 1 },
      { id: 'invalid', name: 'Bad' }, // missing colors
    ];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toHaveLength(1);
    expect(result.current.presets[0].name).toBe('Good');
  });

  it('validates hex format in presets (#RRGGBB required)', () => {
    const data = [
      {
        id: 'bad-hex',
        name: 'Bad Hex',
        colors: [{ name: 'Red', hex: 'FF0000', transmission_distance: 1 }],
        createdAt: 1,
        updatedAt: 1,
      },
    ];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toHaveLength(0); // filtered out
  });

  it('sets and clears lastPresetId', () => {
    const { result } = renderHook(() => useFilamentStorage());

    act(() => {
      result.current.setLastPresetId('some-id');
    });
    expect(result.current.lastPresetId).toBe('some-id');
    expect(localStorage.getItem(LAST_PRESET_KEY)).toBe('some-id');

    act(() => {
      result.current.setLastPresetId(null);
    });
    expect(result.current.lastPresetId).toBeNull();
    expect(localStorage.getItem(LAST_PRESET_KEY)).toBeNull();
  });

  it('handles localStorage quota exceeded on save', () => {
    const { result } = renderHook(() => useFilamentStorage());

    // Simulate quota exceeded
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });

    // Should not throw
    act(() => {
      result.current.savePreset('Test', sampleColors);
    });

    expect(result.current.presets).toHaveLength(1);
  });
});
