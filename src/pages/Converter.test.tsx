import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Converter from './Converter';
import { batchDownloadSTL, getFilamentPresets, getFilamentPreview } from '../api/client';
import { filamentCatalog } from '../test/filamentCatalog';

vi.mock('../hooks/useBackendReady', () => ({ useBackendReady: () => true }));
vi.mock('../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../api/client')>(),
  getFilamentPresets: vi.fn(),
  getFilamentPreview: vi.fn(),
  batchDownloadSTL: vi.fn(),
}));

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getFilamentPresets).mockResolvedValue(structuredClone(filamentCatalog));
  vi.mocked(getFilamentPreview).mockResolvedValue({
    image: '', colorMatrix: [], stats: { colorCount: 5, combinationCount: 625 },
    imageDimensions: { width: 1, height: 1 }, warnings: [],
  });
  vi.mocked(batchDownloadSTL).mockResolvedValue(undefined);
});

describe('converter backing configuration', () => {
  it('sends the selected backing from the settings panel through batch downloads', async () => {
    render(<Converter />);
    await waitFor(() => expect(screen.queryByText('Loading filaments…')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Dark backing' }));
    fireEvent.click(screen.getByRole('button', { name: 'Batch Processing' }));
    const picker = screen.getByRole('button', { name: /Click to Select Images/ }).parentElement!.querySelector('input')!;
    const file = new File(['image'], 'sample.png', { type: 'image/png' });
    fireEvent.change(picker, { target: { files: [file] } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Download All STLs' })));
    expect(batchDownloadSTL).toHaveBeenLastCalledWith([file], expect.objectContaining({ backingMode: 'black', whiteBackingLayers: 3 }), expect.any(AbortSignal));
    fireEvent.click(screen.getByRole('button', { name: 'Light backing' }));
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Download All STLs' })));
    expect(batchDownloadSTL).toHaveBeenLastCalledWith([file], expect.objectContaining({ backingMode: 'white', whiteBackingLayers: 3 }), expect.any(AbortSignal));
  });
});
