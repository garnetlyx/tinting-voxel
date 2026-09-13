import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilamentColorRow, hasMeasuredParams, measuredParamsDescription } from './FilamentColorRow';
import type { FilamentColorConfig } from '../api/types';

// The i18n runtime resolves keys to themselves without a provider wrapper
// in this suite; assertions target structure and behavior, not copy.

const baseConfig: FilamentColorConfig = {
  name: 'G',
  hex: '#9A9D9C',
  transmission_distance: 1.7,
};

const measuredConfig: FilamentColorConfig = {
  ...baseConfig,
  td_rgb: [2.23, 1.69, 1.19],
  td_neutral: 7.3,
};

describe('hasMeasuredParams', () => {
  it('false for plain custom colors', () => {
    expect(hasMeasuredParams(baseConfig)).toBe(false);
  });
  it('true when td_rgb or td_neutral present', () => {
    expect(hasMeasuredParams(measuredConfig)).toBe(true);
    expect(hasMeasuredParams({ ...baseConfig, td_neutral: 7.3 })).toBe(true);
    expect(hasMeasuredParams({ ...baseConfig, td_rgb: [1, 2, 3] })).toBe(true);
  });
});

describe('measuredParamsDescription', () => {
  it('lists both measured fields', () => {
    expect(measuredParamsDescription(measuredConfig)).toBe('td_rgb (2.23, 1.69, 1.19) · TD1S 7.3');
  });
  it('lists only the field present', () => {
    expect(measuredParamsDescription({ ...baseConfig, td_neutral: 7.3 })).toBe('TD1S 7.3');
  });
});

describe('FilamentColorRow measured-color locking', () => {
  const noop = () => {};

  it('disables the td input while measured fields drive the color', () => {
    render(
      <FilamentColorRow
        config={measuredConfig}
        index={0}
        onChange={noop}
        onRemove={noop}
        canRemove
        existingLabels={['G']}
      />
    );
    const tdInput = screen.getByTitle(/td_rgb \(2\.23, 1\.69, 1\.19\) · TD1S 7\.3/) as HTMLInputElement;
    expect(tdInput.disabled).toBe(true);
  });

  it('keeps the td input editable for custom colors', () => {
    render(
      <FilamentColorRow
        config={baseConfig}
        index={0}
        onChange={noop}
        onRemove={noop}
        canRemove
        existingLabels={['G']}
      />
    );
    const tdInput = screen.getByDisplayValue('1.7') as HTMLInputElement;
    expect(tdInput.disabled).toBe(false);
  });

  it('downgrade button clears measured fields so the scalar td takes over', () => {
    const onChange = vi.fn();
    render(
      <FilamentColorRow
        config={measuredConfig}
        index={0}
        onChange={onChange}
        onRemove={noop}
        canRemove
        existingLabels={['G']}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /convert to custom|改为自定义/i }));
    expect(onChange).toHaveBeenCalledWith(0, expect.objectContaining({
      td_rgb: undefined,
      td_neutral: undefined,
      transmission_distance: 1.7,
      hex: '#9A9D9C',
    }));
  });

  it('renders no downgrade button for custom colors', () => {
    render(
      <FilamentColorRow
        config={baseConfig}
        index={0}
        onChange={noop}
        onRemove={noop}
        canRemove
        existingLabels={['G']}
      />
    );
    expect(screen.queryByTitle(/convert to custom|改为自定义/i)).toBeNull();
  });
});
