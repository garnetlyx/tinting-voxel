import { describe, it, expect } from 'vitest';
import { DEFAULT_PRESETS } from './types';
import type { FilamentPreset, FilamentColorConfig } from './types';

describe('DEFAULT_PRESETS', () => {
  it('contains the built-in filament presets', () => {
    expect(DEFAULT_PRESETS).toHaveProperty('bambu_cmyk');
    expect(DEFAULT_PRESETS).toHaveProperty('bambu_cmyk_calibrated');
    expect(DEFAULT_PRESETS).toHaveProperty('bambu_cmyk_phase6');
    expect(DEFAULT_PRESETS).toHaveProperty('clear_cmyk');
  });

  it('bambu_cmyk has 4 colors', () => {
    expect(DEFAULT_PRESETS.bambu_cmyk).toHaveLength(4);
  });

  it('clear_cmyk has 4 colors', () => {
    expect(DEFAULT_PRESETS.clear_cmyk).toHaveLength(4);
  });

  it('bambu_cmyk_calibrated has 5 colors', () => {
    expect(DEFAULT_PRESETS.bambu_cmyk_calibrated).toHaveLength(5);
  });

  it('bambu_cmyk_phase6 has 5 colors', () => {
    expect(DEFAULT_PRESETS.bambu_cmyk_phase6).toHaveLength(5);
  });

  const presetNames: FilamentPreset[] = ['bambu_cmyk', 'bambu_cmyk_calibrated', 'bambu_cmyk_phase6', 'clear_cmyk'];

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

      it('has valid calibrated parameters when provided', () => {
        DEFAULT_PRESETS[preset].forEach((color: FilamentColorConfig) => {
          if (color.alpha !== undefined) expect(color.alpha).toBeGreaterThan(0);
          if (color.k !== undefined) expect(color.k).toBeGreaterThanOrEqual(0);
          if (color.td_scale !== undefined) expect(color.td_scale).toBeGreaterThan(0);
          if (color.td_gamma !== undefined) expect(color.td_gamma).toBeGreaterThan(0);
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

  it('matches the backend calibrated preset values', () => {
    expect(DEFAULT_PRESETS.bambu_cmyk_calibrated).toEqual([
      expect.objectContaining({
        name: 'Cyan',
        transmission_distance: 2.0,
        alpha: 5.751822945330163,
        k: 1.2085100532667932,
        td_scale: 1.0056869820712098,
        td_gamma: 0.4543363851088494,
      }),
      expect.objectContaining({
        name: 'Magenta',
        transmission_distance: 2.9,
        alpha: 5.751822945330163,
        k: 0.35481383708372416,
        td_scale: 1.0056869820712098,
        td_gamma: 0.4543363851088494,
      }),
      expect.objectContaining({
        name: 'Yellow',
        transmission_distance: 5.0,
        alpha: 5.751822945330163,
        k: 8.401071443503248,
        td_scale: 1.0056869820712098,
        td_gamma: 0.4543363851088494,
      }),
      expect.objectContaining({
        name: 'White',
        transmission_distance: 6.1,
        alpha: 5.751822945330163,
        k: 6.523686193460801,
        td_scale: 1.0056869820712098,
        td_gamma: 0.4543363851088494,
      }),
      expect.objectContaining({
        name: 'Key',
        transmission_distance: 0.1,
        alpha: 5.751822945330163,
        k: 5.440433103311526,
        td_scale: 1.0056869820712098,
        td_gamma: 0.4543363851088494,
      }),
    ]);
  });

  it('matches the backend phase6 preset values', () => {
    expect(DEFAULT_PRESETS.bambu_cmyk_phase6).toEqual([
      expect.objectContaining({
        name: 'Cyan',
        transmission_distance: 2.0,
        alpha: 8.08,
        k: 8.13,
        td_scale: 1.48,
        td_gamma: 0.20,
      }),
      expect.objectContaining({
        name: 'Magenta',
        transmission_distance: 2.9,
        alpha: 8.08,
        k: 8.42,
        td_scale: 1.48,
        td_gamma: 0.20,
      }),
      expect.objectContaining({
        name: 'Yellow',
        transmission_distance: 5.0,
        alpha: 8.08,
        k: 3.73,
        td_scale: 1.48,
        td_gamma: 0.20,
      }),
      expect.objectContaining({
        name: 'White',
        transmission_distance: 6.1,
        alpha: 8.08,
        k: 12.39,
        td_scale: 1.48,
        td_gamma: 0.20,
      }),
      expect.objectContaining({
        name: 'Key',
        transmission_distance: 0.1,
        alpha: 8.08,
        k: 17.65,
        td_scale: 1.48,
        td_gamma: 0.20,
      }),
    ]);
  });
});
