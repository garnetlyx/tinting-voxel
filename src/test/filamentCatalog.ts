import type { FilamentColorConfig, FilamentPresetsResponse } from '../api/types';

const regular: FilamentColorConfig[] = [
  { name: 'Cyan', hex: '#00FFFF', transmission_distance: [1, 2, 3] },
  { name: 'Magenta', hex: '#FF00FF', transmission_distance: [3, 1, 2] },
  { name: 'Yellow', hex: '#FFFF00', transmission_distance: [3, 2, 1] },
  { name: 'White', hex: '#FFFFFF', transmission_distance: [4, 4, 4] },
];
const transparent: FilamentColorConfig[] = regular.map(color => ({ ...color, transmission_distance: [5, 6, 7] }));

export const filamentCatalog: FilamentPresetsResponse = {
  presets: [
    { name: 'bambu_cmywk', display_name: 'Bambu CMYWK', colors: [...regular, { name: 'Key', hex: '#000000', transmission_distance: [0.1, 0.2, 0.3] }] },
    { name: 'bambu_cmyw', display_name: 'Bambu CMYW', colors: regular },
    { name: 'clear_cmyg', display_name: 'Clear CMYG', colors: [...transparent.slice(0, 3), { name: 'Grey', hex: '#999999', transmission_distance: [5, 6, 7] }] },
    { name: 'clear_cmyw', display_name: 'Clear CMYW', colors: transparent },
  ],
  defaults: { filament_preset: 'bambu_cmywk', backing_layers: 3, regular_layer_height_mm: 0.08, transparent_layer_height_mm: 0.84 },
  transparency: { td_threshold_mm: 4.5, aggregation: 'mean' },
};
