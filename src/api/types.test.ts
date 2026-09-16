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
  it('classifies preset transparency from the td data (staircase channels or effective scalar threshold)', () => {
    // Clear presets carry staircase-measured per-channel td_rgb (transparent
    // track), even where a channel mean falls below 4.5.
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmyg)).toBe(true);
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmyw)).toBe(true);
    // Bambu raw TDs (0.1-6.1) remap to ~1.8-2.1 mm effective — all below
    // the threshold even though the raw White reading (6.1) exceeds it.
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmywk_phase6)).toBe(false);
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmyw_phase6)).toBe(false);
    // Custom colors classify by their entered td (neutral remap).
    expect(isAllTransparentFilaments([{ name: 'A', hex: '#000000', transmission_distance: 50 }])).toBe(true);
    // Raw td above threshold but remapped below it stays opaque.
    expect(isAllTransparentFilaments([{ name: 'A', hex: '#000000', transmission_distance: 10, td_scale: 0.2, td_gamma: 1 }])).toBe(false);
    expect(isAllTransparentFilaments([])).toBe(false);
  });
  it('keeps frontend initialization equal to the backend catalog fixture', () => {
    expect(DEFAULT_PRESETS).toEqual(canonical);
  });
});
