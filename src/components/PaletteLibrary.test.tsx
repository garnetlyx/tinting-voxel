import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PaletteLibrary } from './PaletteLibrary';
import { DEFAULT_PRESETS } from '../api/types';
import * as api from '../api/client';

describe('PaletteLibrary', () => {
  it('preserves all calibrated material parameters when applying a palette', async () => {
    const colors = DEFAULT_PRESETS.bambu_cmyw_phase6;
    const mock = vi.spyOn(api, 'getPaletteLibrary').mockResolvedValue({ palettes: [{
      id: 'bambu_cmyw_phase6', name: 'Bambu CMYW Phase 6', description: '', colors,
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
