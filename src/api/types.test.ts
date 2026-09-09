import { describe, it, expect } from 'vitest';
import canonical from './__fixtures__/filament-presets.json';
import { DEFAULT_PRESETS } from './types';

describe('built-in presets', () => {
  it('exposes exactly Phase 6 CMYW and Clear CMYWG', () => {
    expect(Object.keys(DEFAULT_PRESETS)).toEqual(['bambu_cmyw_phase6', 'clear_cmywg']);
    expect(DEFAULT_PRESETS.bambu_cmyw_phase6.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W']);
    expect(DEFAULT_PRESETS.clear_cmywg.map(c => c.name[0])).toEqual(['C', 'M', 'Y', 'W', 'G']);
  });
  it('keeps frontend initialization equal to the backend catalog fixture', () => {
    expect(DEFAULT_PRESETS).toEqual(canonical);
  });
});
