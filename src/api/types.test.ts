import { describe, it, expect } from 'vitest';
import canonical from './__fixtures__/filament-presets.json';
import { DEFAULT_PRESETS, isAllTransparentFilaments } from './types';

describe('built-in presets', () => {
  it('exposes exactly Bambu CMYWK, Bambu CMYW, Clear CMYG, and Clear CMYW', () => {
    expect(Object.keys(DEFAULT_PRESETS)).toEqual(['bambu_cmywk_phase6', 'bambu_cmyw_phase6', 'clear_cmyg', 'clear_cmyw']);
    expect(DEFAULT_PRESETS.bambu_cmywk_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'K']);
    expect(DEFAULT_PRESETS.bambu_cmyw_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
    expect(DEFAULT_PRESETS.clear_cmyg.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'G']);
    expect(DEFAULT_PRESETS.clear_cmyw.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
  });
  it('classifies preset transparency from the td data (staircase channels or scalar threshold)', () => {
    // Clear presets carry staircase-measured per-channel td_rgb (transparent
    // track), even where a channel mean falls below 4.5.
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmyg)).toBe(true);
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmyw)).toBe(true);
    // Bambu paper-fitted folds (1.94-2.22) are all below the threshold.
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmywk_phase6)).toBe(false);
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmyw_phase6)).toBe(false);
    // Custom colors classify by their entered td.
    expect(isAllTransparentFilaments([{ name: 'A', hex: '#000000', transmission_distance: 50 }])).toBe(true);
    expect(isAllTransparentFilaments([])).toBe(false);
  });
  it('keeps frontend initialization equal to the backend catalog fixture', () => {
    expect(DEFAULT_PRESETS).toEqual(canonical);
  });
});
