/**
 * Tests for FilamentColorRow under the single-td model: every field is
 * editable (no measured-parameter locking), and edits propagate through
 * onChange with the updated config.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { FilamentColorRow } from './FilamentColorRow';
import type { FilamentColorConfig } from '../api/types';

const baseConfig: FilamentColorConfig = {
  name: 'Cyan',
  hex: '#5489B4',
  transmission_distance: 4.7,
  k: 0,
};

const renderRow = (onChange = vi.fn()) => {
  render(
    <div data-testid="row-container">
      <FilamentColorRow
        config={baseConfig}
        index={0}
        onChange={onChange}
        onRemove={vi.fn()}
        canRemove
        existingLabels={['C']}
      />
    </div>,
  );
  return { onChange };
};

describe('FilamentColorRow (single-td model)', () => {
  it('edits the transmission distance directly — no measured-parameter lock', () => {
    const { onChange } = renderRow();
    const tdInput = screen.getByRole('spinbutton', { name: /transmission distance/i });
    expect(tdInput).not.toBeDisabled();
    fireEvent.change(tdInput, { target: { value: '5.5' } });
    const last = onChange.mock.calls[onChange.mock.calls.length - 1]?.[1];
    expect(last.transmission_distance).toBe(5.5);
  });

  it('keeps k when editing td (preset params survive unrelated edits)', () => {
    const { onChange } = renderRow();
    const tdInput = screen.getByRole('spinbutton', { name: /transmission distance/i });
    fireEvent.change(tdInput, { target: { value: '6' } });
    const last = onChange.mock.calls[onChange.mock.calls.length - 1]?.[1];
    expect(last.k).toBe(0);
    expect(last.hex).toBe('#5489B4');
  });

  it('renders an always-enabled color picker and td input (no locking)', () => {
    const { container } = render(
      <div data-testid="row-container">
        <FilamentColorRow config={baseConfig} index={0} onChange={vi.fn()} onRemove={vi.fn()} canRemove existingLabels={['C']} />
      </div>,
    );
    const picker = container.querySelector('input[type="color"]') as HTMLInputElement;
    expect(picker).not.toBeNull();
    expect(picker).not.toBeDisabled();
    // Hex editing is covered end-to-end by useImageProcessor's
    // updateFilamentColor tests; jsdom's color-input event shim makes the
    // direct change event unreliable here.
  });

  it('renders no lock button (measured-field locking removed)', () => {
    renderRow();
    expect(screen.queryByRole('button', { name: /convert to custom/i })).toBeNull();
  });
});

describe('FilamentColorRow k editor', () => {
  const kConfig: FilamentColorConfig = {
    name: 'Cyan', hex: '#3D79C6', transmission_distance: 0.48447574859816506, k: 8.13,
  };
  const renderK = (onChange = vi.fn()) => {
    render(
      <div><FilamentColorRow config={kConfig} index={0} onChange={onChange} onRemove={vi.fn()} canRemove existingLabels={['C']} /></div>,
    );
    return { onChange };
  };

  it('shows the calibrated k and lets the user edit it', () => {
    const { onChange } = renderK();
    const kInput = screen.getByRole('spinbutton', { name: /absorption gain k/i });
    expect(kInput).toHaveValue(8.13);
    fireEvent.change(kInput, { target: { value: '0' } });
    expect(onChange).toHaveBeenCalledWith(0, expect.objectContaining({ k: 0 }));
  });

  it('defaults k to 0 for colors without one', () => {
    const onChange = vi.fn();
    render(
      <div><FilamentColorRow config={{ name: 'X', hex: '#808080', transmission_distance: 5 }} index={0} onChange={onChange} onRemove={vi.fn()} canRemove existingLabels={['X']} /></div>,
    );
    const kInput = screen.getByRole('spinbutton', { name: /absorption gain k/i }) as HTMLInputElement;
    expect(parseFloat(kInput.value)).toBe(0);
  });
});
