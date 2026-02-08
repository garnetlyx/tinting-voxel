import { describe, it, expect } from 'vitest';
import { DEFAULT_PRESETS } from './types';
import type { FilamentPreset, FilamentColorConfig } from './types';

describe('DEFAULT_PRESETS', () => {
  it('contains bambu_cmyk and clear_cmyk presets', () => {
    expect(DEFAULT_PRESETS).toHaveProperty('bambu_cmyk');
    expect(DEFAULT_PRESETS).toHaveProperty('clear_cmyk');
  });

  it('bambu_cmyk has 4 colors', () => {
    expect(DEFAULT_PRESETS.bambu_cmyk).toHaveLength(4);
  });

  it('clear_cmyk has 4 colors', () => {
    expect(DEFAULT_PRESETS.clear_cmyk).toHaveLength(4);
  });

  const presetNames: FilamentPreset[] = ['bambu_cmyk', 'clear_cmyk'];

  presetNames.forEach(preset => {
    describe(`${preset}`, () => {
      it('has valid hex colors (# + 6 hex chars)', () => {
        const hexRegex = /^#[0-9a-fA-F]{6}$/;
        DEFAULT_PRESETS[preset].forEach((color: FilamentColorConfig) => {
          expect(color.hex).toMatch(hexRegex);
        });
      });

      it('has non-empty names', () => {
        DEFAULT_PRESETS[preset].forEach((color: FilamentColorConfig) => {
          expect(color.name.trim().length).toBeGreaterThan(0);
        });
      });

      it('has positive transmission distances', () => {
        DEFAULT_PRESETS[preset].forEach((color: FilamentColorConfig) => {
          expect(color.transmission_distance).toBeGreaterThan(0);
        });
      });

      it('has unique first letters for color names', () => {
        const labels = DEFAULT_PRESETS[preset].map(c => c.name[0].toUpperCase());
        expect(new Set(labels).size).toBe(labels.length);
      });

      it('has unique hex values', () => {
        const hexValues = DEFAULT_PRESETS[preset].map(c => c.hex.toLowerCase());
        expect(new Set(hexValues).size).toBe(hexValues.length);
      });
    });
  });
});
