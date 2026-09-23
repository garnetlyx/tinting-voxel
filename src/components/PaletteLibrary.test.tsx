import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PaletteLibrary } from './PaletteLibrary';
import { filamentCatalog } from '../test/filamentCatalog';
import * as api from '../api/client';

describe('PaletteLibrary', () => {
  it('preserves all calibrated material parameters when applying a palette', async () => {
    const colors = filamentCatalog.presets[1].colors;
    const mock = vi.spyOn(api, 'getPaletteLibrary').mockResolvedValue({ palettes: [{
      id: 'bambu_cmyw_phase6', name: 'Bambu CMYW', description: '', colors,
    }] });
    const onApplyPalette = vi.fn();
    try {
      render(<PaletteLibrary onApplyPalette={onApplyPalette} />);
      fireEvent.click(screen.getByRole('button', { name: /Palette Library/ }));
      fireEvent.click(await screen.findByRole('button', { name: 'Apply' }));
      expect(onApplyPalette).toHaveBeenCalledWith(colors);
      expect(onApplyPalette.mock.calls[0][0][0]).not.toBe(colors[0]);
    } finally { mock.mockRestore(); }
  });
});
