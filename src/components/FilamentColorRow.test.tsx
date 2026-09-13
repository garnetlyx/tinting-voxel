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
    <table><tbody>
      <FilamentColorRow
        config={baseConfig}
        index={0}
        onChange={onChange}
        onRemove={vi.fn()}
        canRemove
        existingLabels={['C']}
      />
    </tbody></table>,
  );
  return { onChange };
};

describe('FilamentColorRow (single-td model)', () => {
  it('edits the transmission distance directly — no measured-parameter lock', () => {
    const { onChange } = renderRow();
    const tdInput = screen.getByRole('spinbutton');
    expect(tdInput).not.toBeDisabled();
    fireEvent.change(tdInput, { target: { value: '5.5' } });
    const last = onChange.mock.calls[onChange.mock.calls.length - 1]?.[1];
    expect(last.transmission_distance).toBe(5.5);
  });

  it('keeps k when editing td (preset params survive unrelated edits)', () => {
    const { onChange } = renderRow();
    const tdInput = screen.getByRole('spinbutton');
    fireEvent.change(tdInput, { target: { value: '6' } });
    const last = onChange.mock.calls[onChange.mock.calls.length - 1]?.[1];
    expect(last.k).toBe(0);
    expect(last.hex).toBe('#5489B4');
  });

  it('renders an always-enabled color picker and td input (no locking)', () => {
    const { container } = render(
      <table><tbody>
        <FilamentColorRow config={baseConfig} index={0} onChange={vi.fn()} onRemove={vi.fn()} canRemove existingLabels={['C']} />
      </tbody></table>,
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
