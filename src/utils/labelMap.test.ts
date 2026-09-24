import { describe, expect, it } from 'vitest';
import { EMPTY_LABEL, withLabelMap } from './labelMap';

function decode(base64: string): number[] {
  return Array.from(atob(base64), char => char.charCodeAt(0));
}

describe('withLabelMap', () => {
  it('replaces pixel lists with a row-major map of block indices', () => {
    const payload = withLabelMap({
      colorBlocks: [
        { r: 255, g: 0, b: 0, hex: '#ff0000', count: 2, pixels: [{ x: 0, y: 0 }, { x: 2, y: 1 }] },
        { r: 0, g: 0, b: 255, hex: '#0000ff', count: 3, pixels: [{ x: 1, y: 0 }, { x: 0, y: 1 }, { x: 1, y: 1 }] },
      ],
      imageDimensions: { width: 3, height: 2 },
      layerCount: 4,
    });

    expect(payload.colorBlocks).toEqual([
      { r: 255, g: 0, b: 0, hex: '#ff0000' },
      { r: 0, g: 0, b: 255, hex: '#0000ff' },
    ]);
    expect(decode(payload.labelMap)).toEqual([0, 1, EMPTY_LABEL, 1, 1, 0]);
    expect(payload).toMatchObject({ imageDimensions: { width: 3, height: 2 }, layerCount: 4 });
    expect('pixels' in payload.colorBlocks[0]).toBe(false);
  });

  it('encodes grids larger than one conversion chunk', () => {
    const width = 300;
    const height = 200;
    const pixels = Array.from({ length: width * height }, (_, i) => ({ x: i % width, y: Math.floor(i / width) }));
    const payload = withLabelMap({
      colorBlocks: [{ r: 1, g: 2, b: 3, hex: '#010203', count: pixels.length, pixels }],
      imageDimensions: { width, height },
    });
    const cells = decode(payload.labelMap);
    expect(cells).toHaveLength(width * height);
    expect(cells.every(cell => cell === 0)).toBe(true);
  });
});
