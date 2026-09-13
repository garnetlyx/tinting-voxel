import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useImageProcessor } from './useImageProcessor';
import {
  download3MFV2,
  downloadPrintSettings,
  downloadSTLV2,
  processImage,
  simulatePrintPreview,
} from '../api/client';

vi.mock('../api/client', () => ({
  processImage: vi.fn(),
  simulatePrintPreview: vi.fn(),
  downloadCSV: vi.fn(),
  downloadSTLV2: vi.fn(),
  downloadSVGSTLV2: vi.fn(),
  download3MFV2: vi.fn(),
  downloadPrintSettings: vi.fn(),
}));

const mockedProcessImage = vi.mocked(processImage);
const mockedSimulatePrintPreview = vi.mocked(simulatePrintPreview);
const mockedDownloadSTLV2 = vi.mocked(downloadSTLV2);
const mockedDownload3MFV2 = vi.mocked(download3MFV2);
const mockedDownloadPrintSettings = vi.mocked(downloadPrintSettings);

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
      segmentationImage: 'data:image/png;base64,seg',
      mappedBlockColors: [],
      mappedBlendPalette: [],
      imageDimensions: { width: 8, height: 6 },
      printStack: {
        opticalLayerCount: 4,
        whiteBackingLayers: 1,
        totalLayerCount: 5,
        totalHeightMm: 0.4,
      },
    });
    mockedSimulatePrintPreview.mockResolvedValue({
      processedImage: 'data:image/png;base64,sim',
      mappedBlockColors: [],
      mappedBlendPalette: [],
      printStack: {
        opticalLayerCount: 4,
        whiteBackingLayers: 1,
        totalLayerCount: 5,
        totalHeightMm: 0.4,
      },
    });
    mockedDownloadSTLV2.mockResolvedValue(undefined);
    mockedDownload3MFV2.mockResolvedValue(undefined);
    mockedDownloadPrintSettings.mockResolvedValue(undefined);

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

  it('defaults to the Bambu CMYWK filament preset', () => {
    const { result } = renderHook(() => useImageProcessor());

    expect(result.current.filamentPreset).toBe('bambu_cmywk_phase6');
    expect(result.current.filamentColors).toHaveLength(5);
    expect(result.current.layerCount).toBe(4);
    expect(result.current.maxLayerCount).toBe(10);
    expect(result.current.filamentColors.some(color => color.name === 'Key')).toBe(true);
    expect(result.current.filamentColors[0].k).toBe(8.13);
  });

  it('clamps the layer count to the fixed UI maximum', () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => {
      result.current.loadPreset('clear_cmyw');
      result.current.setLayerCount(11);
    });

    expect(result.current.filamentColors).toHaveLength(4);
    expect(result.current.maxLayerCount).toBe(10);
    expect(result.current.layerCount).toBe(10);
  });

  it('raises the default layer height only when every filament classifies as transparent', () => {
    const { result } = renderHook(() => useImageProcessor());

    // Clear preset: every td >= 4.5 -> transparent default 0.84.
    act(() => { result.current.loadPreset('clear_cmyw'); });
    expect(result.current.allTransparent).toBe(true);
    expect(result.current.layerHeight).toBe(0.84);

    // Back to Bambu CMYWK (Key 0.1 blocks) -> non-transparent default 0.08.
    act(() => { result.current.loadPreset('bambu_cmywk_phase6'); });
    expect(result.current.allTransparent).toBe(false);
    expect(result.current.layerHeight).toBe(0.08);
  });

  it('preserves a manually chosen layer height across classification flips', () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => {
      result.current.setLayerHeight(0.3);
      result.current.loadPreset('clear_cmyw');
    });
    expect(result.current.layerHeight).toBe(0.3);

    act(() => { result.current.loadPreset('bambu_cmywk_phase6'); });
    expect(result.current.layerHeight).toBe(0.3);
  });

  it('classifies by the fixed threshold: clear transparent, bambu opaque', () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => { result.current.loadPreset('clear_cmyw'); });
    expect(result.current.allTransparent).toBe(true);
    expect(result.current.layerHeight).toBe(0.84);

    act(() => { result.current.loadPreset('bambu_cmywk_phase6'); });
    expect(result.current.allTransparent).toBe(false);
  });

  it('sends filament config and layer settings when processing an image', async () => {
    const { result } = renderHook(() => useImageProcessor());
    const img = new globalThis.Image() as unknown as HTMLImageElement;

    await act(async () => {
      result.current.handleApplyEdit(img);
    });

    expect(mockedProcessImage).toHaveBeenCalledWith(
      expect.any(File),
      expect.objectContaining({
        mode: 'pixel',
        layerHeight: 0.08,
        layerCount: 4,
        whiteBackingLayers: 1,
        filamentPreset: 'bambu_cmywk_phase6',
      }),
      expect.any(AbortSignal)
    );
  });

  it('ignores a MouseEvent leaked into handleReprocess as the pixel-size override', async () => {
    // onClick={handleReprocess} forwards the click event as the first
    // argument; it must never serialize into pixelSize ("[object Object]").
    const { result } = renderHook(() => useImageProcessor());
    const img = new globalThis.Image() as unknown as HTMLImageElement;

    await act(async () => {
      result.current.handleApplyEdit(img);
    });
    mockedProcessImage.mockClear();

    await act(async () => {
      (result.current.handleReprocess as unknown as (e: unknown) => void)({ type: 'click' });
    });

    const call = mockedProcessImage.mock.calls[0];
    expect(call[1].pixelSize).toBe(result.current.pixelSize);
    expect(call[1].pixelSize).not.toBe('[object Object]');
  });

  it('stores simulated preview data returned by svg mode', async () => {
    mockedProcessImage.mockResolvedValueOnce({
      vectorResults: [{ color: [255, 0, 0], polygons: [], pixel_count: 48, polygon_points: 0 }],
      processedImage: 'data:image/png;base64,svg-sim',
      segmentationImage: 'data:image/png;base64,svg-seg',
      mappedBlendPalette: [
        {
          code: 'CCMY',
          rgb: [100, 100, 100],
          hex: '#646464',
          sourceRgb: [255, 0, 0],
          sourceHex: '#FF0000',
          pixelCount: 48,
          pixelPercent: 100,
        },
      ],
      imageDimensions: { width: 8, height: 6 },
      printStack: {
        opticalLayerCount: 4,
        whiteBackingLayers: 1,
        totalLayerCount: 5,
        totalHeightMm: 0.4,
      },
    });

    const { result } = renderHook(() => useImageProcessor());
    const img = new globalThis.Image() as unknown as HTMLImageElement;

    act(() => {
      result.current.setMode('svg');
    });

    await act(async () => {
      result.current.handleApplyEdit(img);
    });

    expect(result.current.mode).toBe('svg');
    expect(result.current.processedImageUrl).toBe('data:image/png;base64,svg-sim');
    expect(result.current.segmentationImageUrl).toBe('data:image/png;base64,svg-seg');
    expect(result.current.mappedBlendPalette).toHaveLength(1);
    expect(result.current.vectorResults).toHaveLength(1);
  });

  it('preserves filamentPreset for STL downloads when a preset is selected', async () => {
    const { result } = renderHook(() => useImageProcessor());

    await act(async () => {
      await result.current.handleDownloadSTL();
    });

    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmywk_phase6',
      })
    );
    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.not.objectContaining({
        filamentColors: expect.anything(),
      })
    );
  });

  it('preserves filamentPreset for 3MF and print-settings downloads when a preset is selected', async () => {
    const { result } = renderHook(() => useImageProcessor());

    await act(async () => {
      await result.current.handleDownload3MF();
      await result.current.handleDownloadPrintSettings();
    });

    expect(mockedDownload3MFV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmywk_phase6',
      })
    );
    expect(mockedDownloadPrintSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmywk_phase6',
      })
    );
  });

  it('updates pixel size from the editable max dimension while preserving aspect ratio', async () => {
    const { result } = renderHook(() => useImageProcessor());
    const img = new globalThis.Image() as unknown as HTMLImageElement;

    await act(async () => {
      result.current.handleApplyEdit(img);
    });

    act(() => {
      result.current.setMaxDimension(10);
    });

    expect(result.current.pixelSize).toBeCloseTo(1.25);
    expect(result.current.targetWidth).toBeCloseTo(10);
    expect(result.current.targetHeight).toBeCloseTo(7.5);
    expect(result.current.maxDimension).toBeCloseTo(10);
  });

  it('defaults max dimension to the processed image size when it is smaller than 200mm', async () => {
    const { result } = renderHook(() => useImageProcessor());
    const img = new globalThis.Image() as unknown as HTMLImageElement;

    await act(async () => {
      result.current.handleApplyEdit(img);
    });

    expect(result.current.pixelSize).toBeCloseTo(1);
    expect(result.current.targetWidth).toBeCloseTo(8);
    expect(result.current.targetHeight).toBeCloseTo(6);
    expect(result.current.maxDimension).toBeCloseTo(8);
  });

  it('caps the default max dimension at 200mm for larger processed images', async () => {
    mockedProcessImage.mockResolvedValueOnce({
      colorBlocks: [],
      processedImage: 'data:image/png;base64,mock',
      segmentationImage: 'data:image/png;base64,seg',
      mappedBlockColors: [],
      mappedBlendPalette: [],
      imageDimensions: { width: 800, height: 600 },
      printStack: {
        opticalLayerCount: 4,
        whiteBackingLayers: 1,
        totalLayerCount: 5,
        totalHeightMm: 0.4,
      },
    });

    const { result } = renderHook(() => useImageProcessor());
    const img = new globalThis.Image() as unknown as HTMLImageElement;
    // Simulate a large image (800×600) so the 200mm cap kicks in
    Object.defineProperty(img, 'width', { value: 800, configurable: true });
    Object.defineProperty(img, 'height', { value: 600, configurable: true });

    await act(async () => {
      result.current.handleApplyEdit(img);
    });

    expect(result.current.pixelSize).toBeCloseTo(0.25);
    expect(result.current.targetWidth).toBeCloseTo(200);
    expect(result.current.targetHeight).toBeCloseTo(150);
    expect(result.current.maxDimension).toBeCloseTo(200);
  });

  it('falls back to filamentColors after the preset is edited into a custom config', async () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => {
      result.current.updateFilamentColor(0, {
        name: 'Cyan',
        hex: '#0086D6',
        transmission_distance: 3.25,
      });
    });

    await act(async () => {
      await result.current.handleDownloadSTL();
    });

    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentColors: expect.arrayContaining([
          expect.objectContaining({
            transmission_distance: 3.25,
          }),
        ]),
      })
    );
    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.not.objectContaining({
        filamentPreset: expect.anything(),
      })
    );
  });

  it('inherits family blend params when adding a custom color to a calibrated preset', () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => {
      result.current.loadPreset('bambu_cmyw_phase6');
      result.current.addFilamentColor();
    });

    expect(result.current.filamentColors).toHaveLength(5);
    // New colors default to plain Beer-Lambert — no silent k inheritance.
    const added = result.current.filamentColors[4];
    expect(added.k).toBeUndefined();
  });

  it('preserves calibrated material parameters when editing a calibrated preset', async () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => {
      result.current.loadPreset('bambu_cmyw_phase6');
      result.current.updateFilamentColor(0, {
        name: 'Cyan',
        hex: '#3D79C6',
        transmission_distance: 2.1,
      });
    });

    await act(async () => {
      await result.current.handleDownloadSTL();
    });

    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentColors: expect.arrayContaining([
          expect.objectContaining({
            name: 'Cyan',
            transmission_distance: 2.1,
            k: 8.13,
          }),
        ]),
      })
    );
  });
});
