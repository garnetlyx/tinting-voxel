import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PresetSelector } from './PresetSelector';
import { filamentCatalog } from '../test/filamentCatalog';

describe('PresetSelector', () => {
  it('uses only API options and selects a supplied preset', () => {
    const onPresetChange = vi.fn();
    const presets = [...filamentCatalog.presets, { name: 'new-material', display_name: 'New Material', colors: [] }];
    render(<PresetSelector presets={presets} selectedPreset="bambu_cmywk_phase6" onPresetChange={onPresetChange} />);
    expect(screen.getAllByRole('option').map(option => option.textContent)).toEqual(['Bambu CMYWK', 'Bambu CMYW', 'Clear CMYG', 'Clear CMYW', 'New Material']);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'new-material' } });
    expect(onPresetChange).toHaveBeenCalledWith('new-material');
  });
  it('shows custom as a non-selectable state', () => {
    render(<PresetSelector presets={filamentCatalog.presets} selectedPreset={null} onPresetChange={vi.fn()} />);
    expect(screen.getByRole('option', { name: 'Custom' })).toBeDisabled();
  });
});
