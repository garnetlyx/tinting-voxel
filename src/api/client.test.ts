import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  processImage,
  downloadCSV,
  getFilamentPresets,
  downloadSTLV2,
  getFilamentPreview,
  downloadSVGSTLV2,
  download3MFV2,
  downloadPrintSettings,
  batchProcessImages,
  batchDownloadSTL,
  getPaletteLibrary,
} from './client';
import type {
  ColorBlock,
  DownloadSTLParamsV2,
  FilamentPreviewParams,
  PrintSettingsParams,
} from './types';

// Mock DOM APIs used by downloadBlobAsFile
const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
const mockRevokeObjectURL = vi.fn();
const mockClick = vi.fn();
const mockAppendChild = vi.fn();
const mockRemoveChild = vi.fn();
const mockCreateElement = vi.fn(() => ({
  href: '',
  download: '',
  click: mockClick,
}));

beforeEach(() => {
  vi.useFakeTimers();
  globalThis.URL.createObjectURL = mockCreateObjectURL;
  globalThis.URL.revokeObjectURL = mockRevokeObjectURL;
  document.createElement = mockCreateElement as unknown as typeof document.createElement;
  document.body.appendChild = mockAppendChild;
  document.body.removeChild = mockRemoveChild;
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function mockFetchResponse(body: unknown, ok = true, status = 200) {
  const response = {
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
    blob: vi.fn().mockResolvedValue(new Blob(['test'])),
  };
  globalThis.fetch = vi.fn().mockResolvedValue(response);
  return response;
}

function mockFetchError(detail: string, status = 400) {
  const response = {
    ok: false,
    status,
    json: vi.fn().mockResolvedValue({ detail }),
    blob: vi.fn().mockResolvedValue(new Blob()),
  };
  globalThis.fetch = vi.fn().mockResolvedValue(response);
  return response;
}

describe('processImage', () => {
  it('sends FormData with pixel mode params', async () => {
    const mockResponse = {
      colorBlocks: [],
      processedImage: 'data:image/png;base64,abc',
      imageDimensions: { width: 100, height: 100 },
    };
    mockFetchResponse(mockResponse);

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    const result = await processImage(file, {
      mode: 'pixel',
      pixelSize: 0.08,
      pixelParams: { maxColors: 10, colorThreshold: 50 },
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/process-image',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result).toEqual(mockResponse);
  });

  it('sends FormData with svg mode params', async () => {
    const mockResponse = {
      vectorResults: [],
      processedImage: 'data:image/png;base64,abc',
      imageDimensions: { width: 100, height: 100 },
    };
    mockFetchResponse(mockResponse);

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    const result = await processImage(file, {
      mode: 'svg',
      pixelSize: 0.08,
      svgParams: { epsilon: 2.0, minArea: 100, numColors: 8 },
    });

    expect(result).toEqual(mockResponse);
  });

  it('throws error on failed response', async () => {
    mockFetchError('Image too large');

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await expect(
      processImage(file, { mode: 'pixel', pixelSize: 0.08 })
    ).rejects.toThrow('Image too large');
  });

  it('passes AbortSignal to fetch', async () => {
    mockFetchResponse({ colorBlocks: [], processedImage: '', imageDimensions: { width: 0, height: 0 } });

    const controller = new AbortController();
    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await processImage(file, { mode: 'pixel', pixelSize: 0.08 }, controller.signal);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/process-image',
      expect.objectContaining({ signal: controller.signal })
    );
  });

  it('handles non-JSON error response gracefully', async () => {
    const response = {
      ok: false,
      status: 500,
      json: vi.fn().mockRejectedValue(new Error('not json')),
    };
    globalThis.fetch = vi.fn().mockResolvedValue(response);

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await expect(
      processImage(file, { mode: 'pixel', pixelSize: 0.08 })
    ).rejects.toThrow('Failed to process image');
  });
});

describe('downloadCSV', () => {
  it('sends color blocks and triggers download', async () => {
    mockFetchResponse(null);

    const blocks: ColorBlock[] = [
      { r: 255, g: 0, b: 0, count: 10, pixels: [{ x: 0, y: 0 }], hex: '#FF0000' },
    ];
    await downloadCSV(blocks);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/download-csv',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
  });

  it('throws on error response', async () => {
    mockFetchError('No color blocks');
    await expect(downloadCSV([])).rejects.toThrow('No color blocks');
  });
});

describe('getFilamentPresets', () => {
  it('fetches presets from V2 API', async () => {
    const mockPresets = { presets: [{ name: 'bambu_cmyk', display_name: 'Bambu', colors: [] }] };
    mockFetchResponse(mockPresets);

    const result = await getFilamentPresets();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v2/filament-presets',
      expect.objectContaining({ method: 'GET' })
    );
    expect(result).toEqual(mockPresets);
  });
});

describe('downloadSTLV2', () => {
  it('sends V2 params and triggers download', async () => {
    mockFetchResponse(null);

    const params: DownloadSTLParamsV2 = {
      colorBlocks: [],
      layerHeight: 0.08,
      pixelSize: 0.08,
      layerCount: 4,
      imageDimensions: { width: 100, height: 100 },
      filamentColors: [{ name: 'Cyan', hex: '#0086D6', transmission_distance: 3.0 }],
    };
    await downloadSTLV2(params);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v2/download-stl',
      expect.objectContaining({ method: 'POST' })
    );
    expect(mockClick).toHaveBeenCalled();
  });
});

describe('getFilamentPreview', () => {
  it('posts preview params and returns response', async () => {
    const mockPreview = {
      image: 'data:image/png;base64,abc',
      colorMatrix: [],
      stats: { colorCount: 4, combinationCount: 64 },
      imageDimensions: { width: 200, height: 200 },
      warnings: [],
    };
    mockFetchResponse(mockPreview);

    const params: FilamentPreviewParams = {
      filamentColors: [{ name: 'Cyan', hex: '#0086D6', transmission_distance: 3.0 }],
      layerCount: 4,
      layerHeight: 0.08,
    };
    const result = await getFilamentPreview(params);
    expect(result).toEqual(mockPreview);
  });
});

describe('downloadSVGSTLV2', () => {
  it('sends SVG V2 params and triggers download', async () => {
    mockFetchResponse(null);

    await downloadSVGSTLV2({
      vectorResults: [],
      layerHeight: 0.08,
      pixelSize: 0.08,
      layerCount: 4,
      imageDimensions: { width: 100, height: 100 },
      filamentColors: [],
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v2/download-svg-stl',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('download3MFV2', () => {
  it('sends 3MF params and triggers download', async () => {
    mockFetchResponse(null);

    await download3MFV2({
      colorBlocks: [],
      layerHeight: 0.08,
      pixelSize: 0.08,
      layerCount: 4,
      imageDimensions: { width: 100, height: 100 },
      filamentColors: [],
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v2/download-3mf',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('downloadPrintSettings', () => {
  it('sends print settings params and triggers download', async () => {
    mockFetchResponse(null);

    const params: PrintSettingsParams = {
      layerHeight: 0.08,
      pixelSize: 0.08,
      layerCount: 4,
      imageDimensions: { width: 100, height: 100 },
      filamentColors: [],
    };
    await downloadPrintSettings(params);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v2/print-settings',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('batchProcessImages', () => {
  it('sends multiple files as FormData', async () => {
    const mockResponse = {
      results: [],
      totalImages: 2,
      successCount: 2,
      errorCount: 0,
    };
    mockFetchResponse(mockResponse);

    const files = [
      new File(['a'], 'a.png', { type: 'image/png' }),
      new File(['b'], 'b.png', { type: 'image/png' }),
    ];
    const result = await batchProcessImages(files, {
      maxColors: 10,
      colorThreshold: 50,
      pixelSize: 0.08,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/batch/process',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result).toEqual(mockResponse);
  });
});

describe('batchDownloadSTL', () => {
  it('sends batch download params and triggers download', async () => {
    mockFetchResponse(null);

    const files = [new File(['a'], 'a.png', { type: 'image/png' })];
    await batchDownloadSTL(files, {
      maxColors: 10,
      colorThreshold: 50,
      pixelSize: 0.08,
      layerHeight: 0.08,
      layerCount: 4,
      basePlateThickness: 0,
      doubleSided: false,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/batch/download-stl',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('getPaletteLibrary', () => {
  it('fetches palettes without category filter', async () => {
    const mockPalettes = { palettes: [], categories: {} };
    mockFetchResponse(mockPalettes);

    const result = await getPaletteLibrary();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/palettes/',
      expect.objectContaining({ method: 'GET' })
    );
    expect(result).toEqual(mockPalettes);
  });

  it('fetches palettes with category filter', async () => {
    mockFetchResponse({ palettes: [], categories: {} });

    await getPaletteLibrary('standard');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/palettes/?category=standard',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('encodes category parameter', async () => {
    mockFetchResponse({ palettes: [], categories: {} });

    await getPaletteLibrary('my category');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/palettes/?category=my%20category',
      expect.objectContaining({ method: 'GET' })
    );
  });
});
