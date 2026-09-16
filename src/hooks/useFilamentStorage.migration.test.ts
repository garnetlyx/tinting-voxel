/**
 * Migration tests: persisted presets saved under the retired schema (with
 * alpha/td_neutral) load and import as clean
 * hex+td(+td_rgb)(+k)(+alpha_s/td_scale/td_gamma) objects, so outbound
 * payloads never hit the backend's extra='forbid' rejection. td_rgb is the
 * per-channel td schema and survives; td_scale/td_gamma/alpha_s are the
 * current paper scalar-form fields and survive; the retired mode-dispatch
 * fields (alpha, td_neutral) are stripped.
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useFilamentStorage } from './useFilamentStorage';

const OLD_SCHEMA_PRESET = {
  id: 'legacy-1',
  name: 'Legacy Clear',
  createdAt: 1,
  updatedAt: 1,
  colors: [
    {
      name: 'Cyan',
      hex: '#5489B4',
      transmission_distance: 4.7,
      alpha: 12.0,
      k: 1.93,
      td_rgb: [1.04, 4.66, 8.3],
      td_neutral: 48.9,
      td_scale: 1.0,
      td_gamma: 1.0,
    },
    { name: 'Magenta', hex: '#DE5740', transmission_distance: 6.3, alpha: 12.0 },
  ],
};

describe('useFilamentStorage schema migration', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('tinting-voxel_filament_presets', JSON.stringify([OLD_SCHEMA_PRESET]));
  });

  it('strips retired fields from persisted presets on load', () => {

    const { result } = renderHook(() => useFilamentStorage());
    expect(result.current.presets).toHaveLength(1);
    const colors = result.current.presets[0].colors;
    expect(colors[0]).toEqual({
      name: 'Cyan',
      hex: '#5489B4',
      transmission_distance: 4.7,
      td_rgb: [1.04, 4.66, 8.3],
      k: 1.93,
      td_scale: 1.0,
      td_gamma: 1.0,
    });
    expect(colors[1]).toEqual({ name: 'Magenta', hex: '#DE5740', transmission_distance: 6.3 });
  });

  it('strips retired fields from imported presets', () => {

    const { result } = renderHook(() => useFilamentStorage());
    const res = result.current.importPresets(JSON.stringify([OLD_SCHEMA_PRESET]));
    expect(res.imported).toBe(1);
    const imported = result.current.presets[result.current.presets.length - 1];
    expect(imported!.colors[0]).toEqual({
      name: 'Cyan',
      hex: '#5489B4',
      transmission_distance: 4.7,
      td_rgb: [1.04, 4.66, 8.3],
      k: 1.93,
      td_scale: 1.0,
      td_gamma: 1.0,
    });
  });
});
