import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ParameterPanel } from './ParameterPanel';

describe('ParameterPanel', () => {
  const defaultProps = {
    mode: 'pixel' as const,
    onModeChange: vi.fn(),
    maxColors: 10,
    colorThreshold: 50,
    onMaxColorsChange: vi.fn(),
    onColorThresholdChange: vi.fn(),
    epsilon: 2,
    minArea: 4.0,
    numColors: 8,
    onEpsilonChange: vi.fn(),
    onMinAreaChange: vi.fn(),
    onNumColorsChange: vi.fn(),
    layerHeight: 0.08,
    layerCount: 4,
    maxLayerCount: 8,
    pixelSize: 0.4,
    onLayerHeightChange: vi.fn(),
    onLayerCountChange: vi.fn(),
    onPixelSizeChange: vi.fn(),
    detailSize: 0.4,
    onDetailSizeChange: vi.fn(),
    targetWidth: 10,
    targetHeight: 7.5,
    maxDimension: 10,
    onMaxDimensionChange: vi.fn(),
    whiteBackingLayers: 1,
    onWhiteBackingLayersChange: vi.fn(),
    filamentColors: [
      { name: 'Cyan', hex: '#3D79C6', transmission_distance: 0.2 },
      { name: 'Magenta', hex: '#B3356E', transmission_distance: 0.2 },
      { name: 'Yellow', hex: '#FFE665', transmission_distance: 0.2 },
      { name: 'Grey', hex: '#9A9D9C', transmission_distance: 0.2 },
    ],
    backingFilament: 'G',
    onBackingFilamentChange: vi.fn(),
        printStack: {
      opticalLayerCount: 4,
      whiteBackingLayers: 1,
      backingFilament: 'G',
      totalLayerCount: 5,
      totalHeightMm: 0.4,
    },
    onReprocess: vi.fn(),
    processing: false,
    hasImage: true,
    onTransparentTdThresholdChange: vi.fn(),
  };

  it('lets users type a multi-digit max dimension before committing', async () => {
    const user = userEvent.setup();
    const onMaxDimensionChange = vi.fn();

    render(
      <ParameterPanel
        {...defaultProps}
        onMaxDimensionChange={onMaxDimensionChange}
      />
    );

    const input = screen.getByLabelText(/Max Dimension/i);

    await user.clear(input);
    await user.type(input, '2');
    expect(input).toHaveValue(2);
    expect(onMaxDimensionChange).not.toHaveBeenCalled();

    await user.type(input, '00');
    expect(input).toHaveValue(200);

    await user.tab();
    expect(onMaxDimensionChange).toHaveBeenCalledWith(200);
  });

  it('shows the current filament-aware upper limit for color layers', () => {
    render(<ParameterPanel {...defaultProps} />);

    const slider = screen.getByRole('slider', { name: 'Color Layers' });
    expect(slider).toHaveValue('4');
    expect(slider).toHaveAttribute('max', '8');
    expect(screen.getByRole('slider', { name: 'Layer Height' })).toHaveAttribute('aria-valuetext', '0.08 mm');
    expect(screen.getByText('Up to 8 for the current filament set')).toBeInTheDocument();
  });

  it('picks the backing filament from the current set', async () => {
    const user = userEvent.setup();
    const onBackingFilamentChange = vi.fn();
    render(<ParameterPanel {...defaultProps} onBackingFilamentChange={onBackingFilamentChange} />);

    const picker = within(screen.getByRole('group', { name: 'Backing filament' }));
    expect(picker.getAllByRole('button').map(button => button.textContent)).toEqual(['Cyan', 'Magenta', 'Yellow', 'Grey']);
    expect(picker.getByRole('button', { name: 'Grey' })).toHaveAttribute('aria-pressed', 'true');
    expect(picker.getByRole('button', { name: 'Yellow' })).toHaveAttribute('aria-pressed', 'false');

    await user.click(picker.getByRole('button', { name: 'Cyan' }));
    expect(onBackingFilamentChange).toHaveBeenCalledWith('C');
  });

  it('disables the backing filament choice without backing layers', () => {
    render(<ParameterPanel {...defaultProps} whiteBackingLayers={0} />);

    const buttons = within(screen.getByRole('group', { name: 'Backing filament' })).getAllByRole('button');
    expect(buttons.every(button => button.hasAttribute('disabled'))).toBe(true);
  });

  it('keeps the Local-photo 200 mm pixel pitch selectable without rounding it', () => {
    const pixelSize = 200 / 1270;
    const { container } = render(<ParameterPanel {...defaultProps} pixelSize={pixelSize} />);
    const slider = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="range"]'))
      .find(input => Number(input.value) === pixelSize);

    expect(slider).toBeDefined();
    expect(Number(slider?.min)).toBeLessThan(pixelSize);
    expect(slider?.step).toBe('any');
  });
});
