import { describe, it, expect } from 'vitest';
import canonical from './__fixtures__/filament-presets.json';
import { DEFAULT_PRESETS, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM, isAllTransparentFilaments } from './types';

describe('built-in presets', () => {
  it('exposes exactly Bambu CMYWK, Bambu CMYW, and Clear CMYW', () => {
    expect(Object.keys(DEFAULT_PRESETS)).toEqual(['bambu_cmywk_phase6', 'bambu_cmyw_phase6', 'clear_cmyw']);
    expect(DEFAULT_PRESETS.bambu_cmywk_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'K']);
    expect(DEFAULT_PRESETS.bambu_cmyw_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
    expect(DEFAULT_PRESETS.clear_cmyw.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
  });
  it('classifies preset transparency from the stored td at the default threshold', () => {
    // All clear CMYW tds meet 4.5 (lowest is cyan at 4.7).
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmyw, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM)).toBe(true);
    // Bambu folded tds (0.27-0.61) are all below the threshold.
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmywk_phase6, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM)).toBe(false);
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmyw_phase6, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM)).toBe(false);
    // Custom colors classify by their entered td.
    expect(isAllTransparentFilaments([{ name: 'A', hex: '#000000', transmission_distance: 50 }], 4.5)).toBe(true);
    expect(isAllTransparentFilaments([], 4.5)).toBe(false);
  });
  it('keeps frontend initialization equal to the backend catalog fixture', () => {
    expect(DEFAULT_PRESETS).toEqual(canonical);
  });
});
