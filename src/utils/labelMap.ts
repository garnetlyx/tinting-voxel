/**
 * Export and preview requests send the model grid as a label map: one byte
 * per cell, row-major and base64-encoded, holding the index of the color
 * block printed there (backend: services/label_map.py). 2M cells travel as
 * ~2.7 MB instead of ~45 MB of pixel coordinates.
 */
import type { ColorBlock, ImageDimensions } from '../api/types';

/** Cells no block covers; block indices are 0..254. */
export const EMPTY_LABEL = 255;

type LabelMapParams = { colorBlocks: ColorBlock[]; imageDimensions: ImageDimensions };

/** Request params with the blocks' pixels replaced by a label map. */
export function withLabelMap<T extends LabelMapParams>({ colorBlocks, ...rest }: T) {
  const { width, height } = rest.imageDimensions;
  const labels = new Uint8Array(width * height).fill(EMPTY_LABEL);
  colorBlocks.forEach((block, index) => {
    for (const { x, y } of block.pixels) {
      if (x < width && y < height) labels[y * width + x] = index;
    }
  });
  return {
    ...rest,
    colorBlocks: colorBlocks.map(({ r, g, b, hex }) => ({ r, g, b, hex })),
    labelMap: toBase64(labels),
  };
}

function toBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}
