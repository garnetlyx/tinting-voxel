import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useImageProcessor } from './useImageProcessor';
import { processImage } from '../api/client';

vi.mock('../api/client', () => ({
  processImage: vi.fn(),
  downloadCSV: vi.fn(),
  downloadSTLV2: vi.fn(),
  downloadSVGSTLV2: vi.fn(),
  download3MFV2: vi.fn(),
  downloadPrintSettings: vi.fn(),
}));

const mockedProcessImage = vi.mocked(processImage);

type MockImageInstance = {
  onload: ((this: GlobalEventHandlers, ev: Event) => unknown) | null;
  onerror: ((this: GlobalEventHandlers, ev: Event | string) => unknown) | null;
  width: number;
  height: number;
  src: string;
  triggerLoad: () => void;
};

describe('useImageProcessor', () => {
  const OriginalImage = globalThis.Image;
  let createdImages: MockImageInstance[] = [];

  beforeEach(() => {
    createdImages = [];

    mockedProcessImage.mockResolvedValue({
      colorBlocks: [],
      processedImage: 'data:image/png;base64,mock',
      imageDimensions: { width: 8, height: 6 },
    });

    Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
      configurable: true,
      value: vi.fn(() => ({ drawImage: vi.fn() })),
    });

    Object.defineProperty(HTMLCanvasElement.prototype, 'toBlob', {
      configurable: true,
      value: (callback: BlobCallback) => callback(new Blob(['x'], { type: 'image/png' })),
    });

    globalThis.Image = class {
      onload: ((this: GlobalEventHandlers, ev: Event) => unknown) | null = null;
      onerror: ((this: GlobalEventHandlers, ev: Event | string) => unknown) | null = null;
      width = 8;
      height = 6;
      private _src = '';

      constructor() {
        const self = this as unknown as MockImageInstance;
        createdImages.push(self);
      }

      set src(value: string) {
        this._src = value;
      }

      get src() {
        return this._src;
      }

      triggerLoad() {
        this.onload?.call(this as unknown as GlobalEventHandlers, new Event('load'));
      }
    } as unknown as typeof Image;
  });

  afterEach(() => {
    globalThis.Image = OriginalImage;
    vi.restoreAllMocks();
  });

  it('does not create any images on mount (no default bootstrap image)', async () => {
    renderHook(() => useImageProcessor());

    // No images should be created on mount since bootstrap logic was removed
    expect(createdImages).toHaveLength(0);
    expect(mockedProcessImage).not.toHaveBeenCalled();
  });
});
