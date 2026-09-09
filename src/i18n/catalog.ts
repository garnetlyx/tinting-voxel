import { english } from './resources';
import { useTranslation } from './index';

// Only system preset IDs have translated labels. Arbitrary colors retain their own codes.
const presetKeys = {
  bambu_cmyw_phase6: 'filaments:bambu_cmyw_phase6',
  clear_cmywg: 'filaments:clear_cmywg',
} as const;

export function usePresetLabel() {
  const { t } = useTranslation();
  return (id: string | null, fallback: string): string => {
    if (id === null) return t('filaments:custom');
    if (!Object.prototype.hasOwnProperty.call(presetKeys, id)) return fallback;
    return t(presetKeys[id as keyof typeof presetKeys]);
  };
}

const parameterKeys = {
  max_colors: 'search:max_colors', color_threshold: 'search:color_threshold',
  num_colors: 'search:num_colors', epsilon: 'search:epsilon', min_area: 'search:min_area',
  detail_size: 'search:detail_size', white_backing_layers: 'search:white_backing_layers', pixel_size: 'search:pixel_size',
} as const;

export function useParameterLabel() {
  const { t } = useTranslation();
  return (code: string): string => Object.prototype.hasOwnProperty.call(parameterKeys, code)
    ? t(parameterKeys[code as keyof typeof parameterKeys]) : code;
}

// Lookup display metadata by identity; unknown catalog entries fall back to their supplied text.
export function usePaletteText() {
  const { i18n } = useTranslation();
  return (key: string, fallback: string): string => {
    if (!Object.prototype.hasOwnProperty.call(english.palettes, key)) return fallback;
    return i18n.getFixedT(null, 'palettes')(key as keyof typeof english.palettes);
  };
}
