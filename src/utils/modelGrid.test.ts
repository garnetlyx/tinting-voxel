import { describe, expect, it } from 'vitest';
import { modelGridSize, modelPitch } from './modelGrid';

const limits = { maxCells: 2_000_000, maxSidePx: 4096 };

describe('model grid policy', () => {
  it('keeps an image within the limits at its own pitch', () => {
    expect(modelPitch(1000, 800, 0.2, 0.42, limits)).toBe(0.2);
    expect(modelGridSize(1000, 800, 0.2, 0.2)).toEqual({ width: 1000, height: 800 });
  });

  it('resamples a 12 MP photo to the cell budget and keeps its physical size', () => {
    const pixelSize = 200 / 4096;
    const pitch = modelPitch(4096, 3072, pixelSize, 0.42, limits);
    const grid = modelGridSize(4096, 3072, pixelSize, pitch);
    expect(grid.width * grid.height).toBeLessThanOrEqual(limits.maxCells);
    expect(grid).toEqual({ width: 1632, height: 1224 });
    expect(grid.width * pitch).toBeLessThanOrEqual(200 + 1e-9);
  });

  it('caps the longest side', () => {
    const pitch = modelPitch(10000, 10, 1, null, limits);
    expect(modelGridSize(10000, 10, 1, pitch).width).toBeLessThanOrEqual(limits.maxSidePx);
  });

  it('uses whole detail-width cells when resampling would land between half and one detail', () => {
    // 500 mm photo with a 0.42 mm detail: the budget alone gives ~0.35 mm cells.
    const pixelSize = 500 / 4096;
    expect(modelPitch(4096, 3072, pixelSize, 0.42, limits)).toBe(0.42);
  });

  it('never snaps native pixel art', () => {
    expect(modelPitch(64, 64, 0.3, 0.42, limits)).toBe(0.3);
  });
});
