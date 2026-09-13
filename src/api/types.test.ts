import { describe, it, expect } from 'vitest';
import canonical from './__fixtures__/filament-presets.json';
import { DEFAULT_PRESETS, isAllTransparentFilaments } from './types';

describe('built-in presets', () => {
  it('exposes exactly Bambu CMYWK, Bambu CMYW, and Clear CMYWG', () => {
    expect(Object.keys(DEFAULT_PRESETS)).toEqual(['bambu_cmywk_phase6', 'bambu_cmyw_phase6', 'clear_cmywg']);
    expect(DEFAULT_PRESETS.bambu_cmywk_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'K']);
    expect(DEFAULT_PRESETS.bambu_cmyw_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
    expect(DEFAULT_PRESETS.clear_cmywg.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'G']);
  });
  it('classifies preset transparency from the stored td at the default threshold', () => {
    // All clear CMYW tds meet 4.5 (lowest is cyan at 4.7).
    expect(isAllTransparentFilaments(DEFAULT_PRESETS.clear_cmyw)).toBe(true);
    // Bambu folded tds (0.27-0.61) are all below the threshold.
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
