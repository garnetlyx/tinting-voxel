import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { FilamentColorRow } from './FilamentColorRow';
import type { FilamentColorConfig } from '../api/types';

const measured: FilamentColorConfig = { name: 'Cyan', hex: '#5489B4', transmission_distance: [1, 4, 10] };

function renderRow(config = measured) {
  const onChange = vi.fn();
  render(<FilamentColorRow config={config} index={0} onChange={onChange} onRemove={vi.fn()} canRemove />);
  return onChange;
}

describe('material TD editor', () => {
  it('starts with one input and expands measured RGB values without changing data', () => {
    const onChange = renderRow();
    expect(screen.getAllByRole('spinbutton')).toHaveLength(1);
    expect(screen.getByRole('spinbutton')).toHaveValue(5);
    expect(screen.queryByRole('textbox')).toBeNull();
    const button = screen.getByRole('button', { name: 'RGB' });
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('R')).toBeVisible();
    expect(screen.getByRole('spinbutton', { name: 'Color 1 B transmission distance' })).toHaveValue(10);
    expect(screen.getAllByRole('spinbutton')).toHaveLength(4);
    fireEvent.click(button);
    expect(screen.queryByText('R')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
    expect(measured.transmission_distance).toEqual([1, 4, 10]);
  });
  it('replaces the measurement only when the single TD is edited', () => {
    const onChange = renderRow();
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '6.5' } });
    expect(onChange).toHaveBeenCalledWith(0, { ...measured, transmission_distance: 6.5 });
  });
  it('preserves the measured TD when changing hex', () => {
    const onChange = renderRow();
    fireEvent.change(screen.getByTitle('Pick color'), { target: { value: '#123456' } });
    expect(onChange).toHaveBeenCalledWith(0, { ...measured, hex: '#123456' });
  });
  it('expands a custom scalar without mutation and converts it only on a channel edit', () => {
    const onChange = renderRow({ ...measured, transmission_distance: 5 });
    fireEvent.click(screen.getByRole('button', { name: 'RGB' }));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole('spinbutton', { name: 'Color 1 R transmission distance' })).toHaveValue(5);
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Color 1 G transmission distance' }), { target: { value: '7' } });
    expect(onChange).toHaveBeenCalledExactlyOnceWith(0, { ...measured, transmission_distance: [5, 7, 5] });
  });
  it('edits a measured channel without overwriting the other channels', () => {
    const onChange = renderRow();
    fireEvent.click(screen.getByRole('button', { name: 'RGB' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Color 1 R transmission distance' }), { target: { value: '2' } });
    expect(onChange).toHaveBeenCalledWith(0, { ...measured, transmission_distance: [2, 4, 10] });
    expect(measured.transmission_distance).toEqual([1, 4, 10]);
  });
  it('permits clearing TD for a new value', () => {
    const onChange = renderRow({ ...measured, transmission_distance: 5 });
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '' } });
    expect(onChange).toHaveBeenCalledWith(0, { ...measured, transmission_distance: 0 });
  });
});
