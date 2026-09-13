import { describe, it, expect } from 'vitest';
import canonical from './__fixtures__/filament-presets.json';
import { DEFAULT_PRESETS, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM, isAllTransparentFilaments } from './types';

describe('built-in presets', () => {
  it('exposes exactly Bambu CMYWK, Bambu CMYW, and Clear CMYWG', () => {
    expect(Object.keys(DEFAULT_PRESETS)).toEqual(['bambu_cmywk_phase6', 'bambu_cmyw_phase6', 'clear_cmywg']);
    expect(DEFAULT_PRESETS.bambu_cmywk_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'K']);
    expect(DEFAULT_PRESETS.bambu_cmyw_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
    expect(DEFAULT_PRESETS.clear_cmywg.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'G']);
  });
  it('classifies preset transparency from TD1S neutral TD at the default threshold', () => {
    // All clear filaments meet 6.7 (lowest is Panchroma grey at 7.3).
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmywg, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM)).toBe(true);
    // Bambu sets are blocked by Key (0.1) / by the opaque tds (max 6.1).
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmywk_phase6, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM)).toBe(false);
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.bambu_cmyw_phase6, DEFAULT_TRANSPARENT_TD_THRESHOLD_MM)).toBe(false);
    // Unmeasured colors fall back to their configured transmission distance.
    expect(isAllTransparentFilaments([{ name: 'A', hex: '#000000', transmission_distance: 50 }], 6.7)).toBe(true);
    expect(isAllTransparentFilaments([], 6.7)).toBe(false);
  });
  it('keeps frontend initialization equal to the backend catalog fixture', () => {
    expect(DEFAULT_PRESETS).toEqual(canonical);
  });
});
