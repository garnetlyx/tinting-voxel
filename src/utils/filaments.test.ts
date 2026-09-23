import { describe, expect, it } from 'vitest';
import { isFilamentColorConfig, isTransmissionDistance, isAllTransparentFilaments } from './filaments';

describe('filament inputs', () => {
  it('accepts exactly one finite scalar or RGB measurement', () => {
    for (const td of [0.001, 0.1, 1000, [1, 2, 3]]) expect(isTransmissionDistance(td)).toBe(true);
    for (const td of [0, -1, NaN, Infinity, 1001, [], [1, 2], [1, 2, 3, 4], [1, 0, 2]]) expect(isTransmissionDistance(td)).toBe(false);
    expect(isFilamentColorConfig({ name: 'A', hex: '#123456', transmission_distance: [1, 2, 3] })).toBe(true);
    expect(isFilamentColorConfig({ name: 'A', hex: '#123456', transmission_distance: 5, extra: 2 })).toBe(false);
  });
  it('classifies by the shared whole-set mean, with equal material weight', () => {
    const colors = [{ name: 'A', hex: '#123456', transmission_distance: 9 }, { name: 'B', hex: '#654321', transmission_distance: [1, 2, 3] as [number, number, number] }];
    expect(isAllTransparentFilaments(colors, { td_threshold_mm: 5.5, aggregation: 'mean' })).toBe(true);
    expect(isAllTransparentFilaments(colors, { td_threshold_mm: 5.6, aggregation: 'mean' })).toBe(false);
    expect(isAllTransparentFilaments([], { td_threshold_mm: 1, aggregation: 'mean' })).toBe(false);
  });
});
