import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
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

  it('uses the latest maxColors value when default image finishes loading', async () => {
    const { result } = renderHook(() => useImageProcessor());

    expect(createdImages).toHaveLength(1);

    act(() => {
      result.current.setMaxColors(12);
    });

    act(() => {
      createdImages[0].triggerLoad();
    });

    await waitFor(() => {
      expect(mockedProcessImage).toHaveBeenCalledTimes(1);
    });

    const [, params] = mockedProcessImage.mock.calls[0];
    expect(params.mode).toBe('pixel');
    expect(params.pixelParams?.maxColors).toBe(12);
  });
});
