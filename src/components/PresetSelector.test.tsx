import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { PresetSelector } from './PresetSelector';

describe('PresetSelector', () => {
  it('shows the built-in presets and custom mode', () => {
    render(
      <PresetSelector
        selectedPreset="bambu_cmywk_phase6"
        onPresetChange={vi.fn()}
      />
    );

    const options = screen.getAllByRole('option').map((option) => option.textContent);

    expect(options).toEqual(['Custom', 'Bambu CMYWK', 'Bambu CMYW', 'Clear CMYG', 'Clear CMYW']);
  });
});
