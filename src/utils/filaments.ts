import type { FilamentColorConfig, FilamentPresetsResponse, TransmissionDistance } from '../api/types';

export function isTransmissionDistance(value: unknown): value is TransmissionDistance {
  const valid = (channel: unknown) => typeof channel === 'number' && Number.isFinite(channel) && channel > 0 && channel <= 1000;
  return Array.isArray(value) ? value.length === 3 && value.every(valid) : valid(value);
}

export function isFilamentColorConfig(value: unknown): value is FilamentColorConfig {
  if (typeof value !== 'object' || value === null) return false;
  const { name, hex, transmission_distance, ...extra } = value as Record<string, unknown>;
  return Object.keys(extra).length === 0
    && typeof name === 'string' && /^[A-Za-z]/.test(name)
    && typeof hex === 'string' && /^#[0-9a-fA-F]{6}$/.test(hex)
    && isTransmissionDistance(transmission_distance);
}

export function isAllTransparentFilaments(
  colors: FilamentColorConfig[],
  transparency: FilamentPresetsResponse['transparency'],
): boolean {
  if (colors.length === 0 || !colors.every(color => isTransmissionDistance(color.transmission_distance))) return false;
  const mean = colors.reduce((sum, { transmission_distance: td }) =>
    sum + (Array.isArray(td) ? td.reduce((total, channel) => total + channel, 0) / td.length : td), 0
  ) / colors.length;
  return mean >= transparency.td_threshold_mm;
}
