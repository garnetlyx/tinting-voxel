import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
    basePlateThickness: 0,
    onBasePlateThicknessChange: vi.fn(),
    doubleSided: false,
    onDoubleSidedChange: vi.fn(),
    printStack: {
      opticalLayerCount: 4,
      whiteBackingLayers: 1,
      totalLayerCount: 5,
      totalHeightMm: 0.4,
    },
    onReprocess: vi.fn(),
    processing: false,
    hasImage: true,
    transparentTdThreshold: 6.7,
    allTransparent: false,
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

    expect(screen.getByText(/Color Layers: 4/i)).toBeInTheDocument();
    expect(screen.getByText(/\(max 8 for current filament set\)/i)).toBeInTheDocument();
  });
});
