import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useImageProcessor } from './useImageProcessor';
import { filamentCatalog } from '../test/filamentCatalog';
import {
  getFilamentPresets,
  getFilamentSet,
  download3MFV2,
  downloadPrintSettings,
  downloadSTLV2,
  processImage,
  simulatePrintPreview,
} from '../api/client';

vi.mock('../api/client', () => ({
  getFilamentPresets: vi.fn(),
  processImage: vi.fn(),
  simulatePrintPreview: vi.fn(),
  downloadCSV: vi.fn(),
  downloadSTLV2: vi.fn(),
  downloadSVGSTLV2: vi.fn(),
  download3MFV2: vi.fn(),
  downloadPrintSettings: vi.fn(),
  getFilamentSet: vi.fn(),
}));

const mockedProcessImage = vi.mocked(processImage);
const mockedSimulatePrintPreview = vi.mocked(simulatePrintPreview);
const mockedDownloadSTLV2 = vi.mocked(downloadSTLV2);
const mockedDownload3MFV2 = vi.mocked(download3MFV2);
const mockedDownloadPrintSettings = vi.mocked(downloadPrintSettings);

async function renderProcessor() {
  const hook = renderHook(() => useImageProcessor());
  await waitFor(() => expect(hook.result.current.filamentCatalogLoading).toBe(false));
  return hook;
}

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
    localStorage.clear();
    vi.mocked(getFilamentPresets).mockResolvedValue(structuredClone(filamentCatalog));
    vi.mocked(getFilamentSet).mockResolvedValue({ maxLayerCount: 10, defaultBackingFilament: 'W' });
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
        whiteBackingLayers: 3,
        backingFilament: 'W',
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
        whiteBackingLayers: 3,
        backingFilament: 'W',
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
    await renderProcessor();

    // No images should be created on mount since bootstrap logic was removed
    expect(createdImages).toHaveLength(0);
    expect(mockedProcessImage).not.toHaveBeenCalled();
  });

  it('defaults to the Bambu CMYWK filament preset', async () => {
    const { result } = await renderProcessor();

    expect(result.current.filamentPreset).toBe('bambu_cmywk');
    expect(result.current.filamentColors).toHaveLength(5);
    expect(result.current.layerCount).toBe(4);
    expect(result.current.maxLayerCount).toBe(10);
    expect(result.current.filamentColors.some(color => color.name === 'Key')).toBe(true);
    expect(result.current.filamentColors).toEqual(filamentCatalog.presets[0].colors);
    expect(result.current.layerHeight).toBe(0.08);
    expect(result.current.whiteBackingLayers).toBe(3);
  });

  it('uses catalog metadata and TD for an arbitrary preset identity', async () => {
    const supplied = structuredClone(filamentCatalog);
    supplied.presets = [{ ...supplied.presets[2], name: 'new-material-set' }];
    supplied.defaults = { ...supplied.defaults, filament_preset: 'new-material-set', backing_layers: 2, regular_layer_height_mm: 0.1, transparent_layer_height_mm: 0.7 };
    vi.mocked(getFilamentPresets).mockResolvedValueOnce(supplied);
    const { result } = await renderProcessor();
    expect(result.current.filamentPreset).toBe('new-material-set');
    expect(result.current.layerHeight).toBe(0.7);
    expect(result.current.whiteBackingLayers).toBe(2);
  });

  it('has no built-in fallback when catalog loading fails and retries the API', async () => {
    vi.mocked(getFilamentPresets).mockRejectedValueOnce(new Error('Catalog unavailable'));
    const { result } = await renderProcessor();
    expect(result.current.filamentCatalogError).toBe('Catalog unavailable');
    expect(result.current.filamentColors).toEqual([]);
    expect(result.current.isFilamentConfigValid).toBe(false);
    act(() => result.current.reloadFilamentCatalog());
    await waitFor(() => expect(result.current.filamentCatalogLoading).toBe(false));
    expect(result.current.filamentColors).toEqual(filamentCatalog.presets[0].colors);
    expect(result.current.isFilamentConfigValid).toBe(true);
  });

  it('initializes a stored custom RGB preset after a delayed catalog response', async () => {
    const customColors = filamentCatalog.presets[2].colors;
    localStorage.setItem('tinting-voxel_filament_presets', JSON.stringify([
      { id: 'saved', name: 'Saved RGB', colors: customColors, createdAt: 1, updatedAt: 1 },
    ]));
    localStorage.setItem('tinting-voxel_last_preset', 'saved');
    let resolveCatalog!: (value: typeof filamentCatalog) => void;
    vi.mocked(getFilamentPresets).mockReturnValueOnce(new Promise(resolve => { resolveCatalog = resolve; }));
    const { result } = renderHook(() => useImageProcessor());
    expect(result.current.filamentColors).toEqual([]);
    expect(result.current.isFilamentConfigValid).toBe(false);
    await act(async () => resolveCatalog(structuredClone(filamentCatalog)));
    expect(result.current.filamentPreset).toBeNull();
    expect(result.current.filamentColors).toEqual(customColors);
    expect(result.current.layerHeight).toBe(filamentCatalog.defaults.transparent_layer_height_mm);
    expect(result.current.whiteBackingLayers).toBe(filamentCatalog.defaults.backing_layers);
  });

  it('clamps the layer count to the fixed UI maximum', async () => {
    const { result } = await renderProcessor();

    act(() => {
      result.current.loadPreset('clear_cmyw');
      result.current.setLayerCount(11);
    });

    expect(result.current.filamentColors).toHaveLength(4);
    expect(result.current.maxLayerCount).toBe(10);
    expect(result.current.layerCount).toBe(10);
  });

  it('uses the layer maximum the backend reports for the filament set', async () => {
    vi.mocked(getFilamentSet).mockResolvedValue({ maxLayerCount: 6, defaultBackingFilament: 'W' });
    const { result } = await renderProcessor();

    act(() => {
      result.current.loadPreset('bambu_cmywk');
      result.current.setLayerCount(10);
    });

    await waitFor(() => expect(result.current.maxLayerCount).toBe(6));
    expect(result.current.layerCount).toBe(6);
    expect(getFilamentSet).toHaveBeenLastCalledWith({ filamentPreset: 'bambu_cmywk' }, expect.any(AbortSignal));
  });

  it('backs each set with its default filament until the user picks one it contains', async () => {
    vi.mocked(getFilamentSet).mockImplementation(async (filament) => ({
      maxLayerCount: 10, defaultBackingFilament: filament.filamentPreset === 'clear_cmyg' ? 'G' : 'W',
    }));
    const { result } = await renderProcessor();

    act(() => result.current.loadPreset('bambu_cmywk'));
    await waitFor(() => expect(result.current.backingFilament).toBe('W'));
    act(() => result.current.setBackingFilament('K'));
    expect(result.current.backingFilament).toBe('K');
    expect(result.current.printStack.backingFilament).toBe('K');

    // Clear CMYG has no Key: its own default (grey) applies.
    act(() => result.current.loadPreset('clear_cmyg'));
    await waitFor(() => expect(result.current.backingFilament).toBe('G'));
    act(() => result.current.loadPreset('bambu_cmywk'));
    await waitFor(() => expect(result.current.backingFilament).toBe('K'));
  });

  it('raises the default layer height when the material set mean exceeds the API threshold', async () => {
    const { result } = await renderProcessor();

    // The API measurements exceed the shared threshold.
    act(() => { result.current.loadPreset('clear_cmyw'); });
    expect(result.current.allTransparent).toBe(true);
    expect(result.current.layerHeight).toBe(0.84);

    // The lower measured TDs restore the ordinary default.
    act(() => { result.current.loadPreset('bambu_cmywk'); });
    expect(result.current.allTransparent).toBe(false);
    expect(result.current.layerHeight).toBe(0.08);
  });

  it('preserves a manually chosen layer height across classification flips', async () => {
    const { result } = await renderProcessor();

    act(() => {
      result.current.setLayerHeight(0.3);
      result.current.loadPreset('clear_cmyw');
    });
    expect(result.current.layerHeight).toBe(0.3);

    act(() => { result.current.loadPreset('bambu_cmywk'); });
    expect(result.current.layerHeight).toBe(0.3);
  });

  it.each([0.08, 0.84])('preserves explicitly chosen default-valued layer height %s across material changes', async (height) => {
    const { result } = await renderProcessor();
    act(() => result.current.setLayerHeight(0.3));
    act(() => result.current.setLayerHeight(height));
    act(() => result.current.loadPreset('clear_cmyw'));
    expect(result.current.layerHeight).toBe(height);
    act(() => result.current.loadPreset('bambu_cmywk'));
    expect(result.current.layerHeight).toBe(height);
  });

  it('keeps the selected backing in automatic preview refreshes, TD edits, and print settings', async () => {
    mockedProcessImage.mockResolvedValueOnce({
      colorBlocks: [{ r: 255, g: 0, b: 0, hex: '#FF0000', count: 1, pixels: [{ x: 0, y: 0 }] }],
      processedImage: 'data:image/png;base64,mock', segmentationImage: 'data:image/png;base64,seg',
      mappedBlockColors: [], mappedBlendPalette: [], imageDimensions: { width: 8, height: 6 },
      printStack: { opticalLayerCount: 4, whiteBackingLayers: 3, backingFilament: 'W', totalLayerCount: 7, totalHeightMm: 0.56 },
    });
    const { result } = await renderProcessor();
    const img = new globalThis.Image() as unknown as HTMLImageElement;
    await act(async () => { result.current.handleApplyEdit(img); });
    mockedSimulatePrintPreview.mockClear();
    act(() => result.current.setBackingFilament('K'));
    await waitFor(() => expect(mockedSimulatePrintPreview).toHaveBeenLastCalledWith(
      expect.objectContaining({ backingFilament: 'K', whiteBackingLayers: 3 }), expect.any(AbortSignal),
    ));
    act(() => result.current.updateFilamentColor(0, { ...result.current.filamentColors[0], transmission_distance: 3.25 }));
    await waitFor(() => expect(mockedSimulatePrintPreview).toHaveBeenLastCalledWith(
      expect.objectContaining({ backingFilament: 'K', filamentColors: expect.arrayContaining([expect.objectContaining({ transmission_distance: 3.25 })]) }), expect.any(AbortSignal),
    ));
    await act(async () => result.current.handleDownloadPrintSettings());
    expect(mockedDownloadPrintSettings).toHaveBeenLastCalledWith(expect.objectContaining({ backingFilament: 'K', whiteBackingLayers: 3 }));
    act(() => result.current.setBackingFilament('W'));
    await waitFor(() => expect(mockedSimulatePrintPreview).toHaveBeenLastCalledWith(
      expect.objectContaining({ backingFilament: 'W', whiteBackingLayers: 3 }), expect.any(AbortSignal),
    ));
  });

  it('classifies from API material measurements and threshold', async () => {
    const { result } = await renderProcessor();

    act(() => { result.current.loadPreset('clear_cmyw'); });
    expect(result.current.allTransparent).toBe(true);
    expect(result.current.layerHeight).toBe(0.84);

    act(() => { result.current.loadPreset('bambu_cmywk'); });
    expect(result.current.allTransparent).toBe(false);
  });

  it('sends filament config and layer settings when processing an image', async () => {
    const { result } = await renderProcessor();
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
        whiteBackingLayers: 3,
        filamentPreset: 'bambu_cmywk',
      }),
      expect.any(AbortSignal)
    );
  });

  it('ignores a MouseEvent leaked into handleReprocess as the pixel-size override', async () => {
    // onClick={handleReprocess} forwards the click event as the first
    // argument; it must never serialize into pixelSize ("[object Object]").
    const { result } = await renderProcessor();
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
      vectorResults: [{ color: [255, 0, 0], regions: [], pixel_count: 48, polygon_points: 0 }],
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
        whiteBackingLayers: 3,
        backingFilament: 'W',
        totalLayerCount: 5,
        totalHeightMm: 0.4,
      },
    });

    const { result } = await renderProcessor();
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

  it('reprocesses pixel geometry before permitting a changed detail width to export', async () => {
    mockedProcessImage.mockResolvedValue({
      colorBlocks: [{ r: 0, g: 0, b: 0, hex: '#000000', count: 48, pixels: [{ x: 0, y: 0 }] }],
      processedImage: 'data:image/png;base64,pixel',
      segmentationImage: 'data:image/png;base64,seg',
      mappedBlockColors: [],
      mappedBlendPalette: [],
      imageDimensions: { width: 8, height: 6 },
      printStack: { opticalLayerCount: 4, whiteBackingLayers: 3, backingFilament: 'W', totalLayerCount: 7, totalHeightMm: 0.56 },
    });
    const { result } = await renderProcessor();
    const img = new globalThis.Image() as unknown as HTMLImageElement;
    await act(async () => result.current.handleApplyEdit(img));
    expect(result.current.renderReady).toBe(true);
    mockedProcessImage.mockClear();

    act(() => result.current.setDetailSize(0.62));
    expect(result.current.renderReady).toBe(false);
    await waitFor(() => expect(mockedProcessImage).toHaveBeenCalledWith(
      expect.any(File), expect.objectContaining({ mode: 'pixel', detailSize: 0.62 }), expect.any(AbortSignal),
    ));
    await waitFor(() => expect(result.current.renderReady).toBe(true));
  });

  it('refreshes SVG preview and export geometry after backing changes', async () => {
    mockedProcessImage.mockResolvedValue({
      vectorResults: [{ color: [255, 0, 0], regions: [{ outer: [[0, 0], [7, 0], [7, 5]], holes: [] }], pixel_count: 48, polygon_points: 3 }],
      processedImage: 'data:image/png;base64,svg',
      segmentationImage: 'data:image/png;base64,seg',
      mappedBlendPalette: [],
      imageDimensions: { width: 8, height: 6 },
      printStack: { opticalLayerCount: 4, whiteBackingLayers: 3, backingFilament: 'W', totalLayerCount: 7, totalHeightMm: 0.56 },
    });
    const { result } = await renderProcessor();
    const img = new globalThis.Image() as unknown as HTMLImageElement;
    act(() => result.current.setMode('svg'));
    await act(async () => result.current.handleApplyEdit(img));
    expect(result.current.renderReady).toBe(true);
    mockedProcessImage.mockClear();

    act(() => result.current.setBackingFilament('K'));
    expect(result.current.renderReady).toBe(false);
    await waitFor(() => expect(mockedProcessImage).toHaveBeenCalledWith(
      expect.any(File), expect.objectContaining({ mode: 'svg', backingFilament: 'K' }), expect.any(AbortSignal),
    ));
    await waitFor(() => expect(result.current.renderReady).toBe(true));
  });

  it('preserves filamentPreset for STL downloads when a preset is selected', async () => {
    const { result } = await renderProcessor();

    await act(async () => {
      await result.current.handleDownloadSTL();
    });

    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmywk',
      })
    );
    expect(mockedDownloadSTLV2).toHaveBeenCalledWith(
      expect.not.objectContaining({
        filamentColors: expect.anything(),
      })
    );
  });

  it('preserves filamentPreset for 3MF and print-settings downloads when a preset is selected', async () => {
    const { result } = await renderProcessor();

    await act(async () => {
      await result.current.handleDownload3MF();
      await result.current.handleDownloadPrintSettings();
    });

    expect(mockedDownload3MFV2).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmywk',
      })
    );
    expect(mockedDownloadPrintSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        filamentPreset: 'bambu_cmywk',
      })
    );
  });

  it('updates pixel size from the editable max dimension while preserving aspect ratio', async () => {
    const { result } = await renderProcessor();
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
    const { result } = await renderProcessor();
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
        whiteBackingLayers: 3,
        backingFilament: 'W',
        totalLayerCount: 5,
        totalHeightMm: 0.4,
      },
    });

    const { result } = await renderProcessor();
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

  it('resamples a large photo to the model grid instead of rejecting it', async () => {
    const { result } = await renderProcessor();
    const img = new globalThis.Image() as unknown as HTMLImageElement;
    Object.defineProperty(img, 'width', { value: 5000, configurable: true });
    Object.defineProperty(img, 'height', { value: 4000, configurable: true });

    await act(async () => {
      result.current.handleApplyEdit(img);
    });

    expect(result.current.error).toBeNull();
    // 20 MP at 200 mm fits the 2M-cell budget as a 1581 x 1264 grid.
    const calls = mockedProcessImage.mock.calls;
    const params = calls[calls.length - 1][1];
    expect(params.pixelSize).toBeCloseTo(200 / 1581, 9);
  });

  it('falls back to filamentColors after the preset is edited into a custom config', async () => {
    const { result } = await renderProcessor();

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

  it('assigns a free code and requires a TD for a new custom color', async () => {
    const { result } = await renderProcessor();

    act(() => {
      result.current.loadPreset('bambu_cmyw');
      result.current.addFilamentColor();
    });

    expect(result.current.filamentColors).toHaveLength(5);
    const added = result.current.filamentColors[4];
    expect(added.name).toBe('A');
    expect(added.transmission_distance).toBe(0);
    expect(result.current.isFilamentConfigValid).toBe(false);
  });

  it('uses the explicitly edited scalar TD when editing a measured preset', async () => {
    const { result } = await renderProcessor();

    act(() => {
      result.current.loadPreset('bambu_cmyw');
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
          }),
        ]),
      })
    );
  });
});
