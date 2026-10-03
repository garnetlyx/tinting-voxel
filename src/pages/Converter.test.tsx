import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Converter from './Converter';
import { batchDownloadSTL, getFilamentPresets, getFilamentPreview, getFilamentSet } from '../api/client';
import { filamentCatalog } from '../test/filamentCatalog';

vi.mock('../hooks/useBackendReady', () => ({ useBackendReady: () => true }));
vi.mock('../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../api/client')>(),
  getFilamentPresets: vi.fn(),
  getFilamentPreview: vi.fn(),
  getFilamentSet: vi.fn(),
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
  vi.mocked(getFilamentSet).mockResolvedValue({ maxLayerCount: 10, defaultBackingFilament: 'W' });
});

describe('converter backing configuration', () => {
  it('sends the backing filament picked in the settings panel through batch downloads', async () => {
    render(<Converter />);
    await waitFor(() => expect(screen.queryByText('Loading filaments…')).not.toBeInTheDocument());
    const backing = within(screen.getByRole('group', { name: 'Backing filament' }));
    await waitFor(() => expect(backing.getByRole('button', { name: 'White' })).toHaveAttribute('aria-pressed', 'true'));
    fireEvent.click(backing.getByRole('button', { name: 'Key' }));
    fireEvent.click(screen.getByRole('button', { name: 'Batch Processing' }));
    const picker = screen.getByRole('button', { name: /Click to Select Images/ }).parentElement!.querySelector('input')!;
    const file = new File(['image'], 'sample.png', { type: 'image/png' });
    fireEvent.change(picker, { target: { files: [file] } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Download All STLs' })));
    expect(batchDownloadSTL).toHaveBeenLastCalledWith([file], expect.objectContaining({ backingFilament: 'K', whiteBackingLayers: 3 }), expect.objectContaining({ signal: expect.any(AbortSignal) }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Backing filament' })).getByRole('button', { name: 'White' }));
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Download All STLs' })));
    expect(batchDownloadSTL).toHaveBeenLastCalledWith([file], expect.objectContaining({ backingFilament: 'W', whiteBackingLayers: 3 }), expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });
});
