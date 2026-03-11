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

  it('defaults to the Phase 6 CMYW filament preset', () => {
    const { result } = renderHook(() => useImageProcessor());

    expect(result.current.filamentPreset).toBe('bambu_cmyw_phase6');
    expect(result.current.filamentColors).toHaveLength(4);
    expect(result.current.filamentColors.some(color => color.name === 'Key')).toBe(false);
    expect(result.current.filamentColors[0].k).toBe(8.13);
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
        filamentPreset: 'bambu_cmyw_phase6',
      }),
      expect.any(AbortSignal)
    );
  });

  it('preserves filamentPreset for STL downloads when a preset is selected', async () => {
    const { result } = renderHook(() => useImageProcessor());

    await act(async () => {
      await result.current.handleDownloadSTL();
    });

    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmyw_phase6',
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
        filamentPreset: 'bambu_cmyw_phase6',
      })
    );
    expect(mockedDownloadPrintSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmyw_phase6',
      })
    );
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

  it('preserves calibrated material parameters when editing a calibrated preset', async () => {
    const { result } = renderHook(() => useImageProcessor());

    act(() => {
      result.current.loadPreset('bambu_cmyk_calibrated');
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
            alpha: 5.751822945330163,
            k: 1.2085100532667932,
            td_scale: 1.0056869820712098,
            td_gamma: 0.4543363851088494,
          }),
        ]),
      })
    );
  });
});
