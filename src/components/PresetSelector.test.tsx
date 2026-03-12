import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { PresetSelector } from './PresetSelector';

describe('PresetSelector', () => {
  it('shows corrected CMYW and CMYWK labels for built-in presets', () => {
    render(
      <PresetSelector
        selectedPreset="bambu_cmyk"
        onPresetChange={vi.fn()}
      />
    );

    const options = screen.getAllByRole('option').map((option) => option.textContent);

    expect(options).toContain('Bambu CMYW');
    expect(options).toContain('Bambu CMYWK Calibrated');
    expect(options).toContain('Bambu CMYWK Phase 6');
    expect(options).toContain('Bambu CMYW Phase 6');
    expect(options).toContain('Clear CMYW');
  });
});
