import type { FilamentLabel, PrintStackInfo } from '../api/types';

export function buildPrintStack(
  layerCount: number,
  layerHeight: number,
  whiteBackingLayers: number,
  backingFilament: FilamentLabel | null,
): PrintStackInfo {
  const opticalLayerCount = layerCount;
  const totalLayerCount = opticalLayerCount + whiteBackingLayers;
  const totalHeightMm = Math.round(totalLayerCount * layerHeight * 100) / 100;

  return {
    opticalLayerCount,
    whiteBackingLayers,
    backingFilament: whiteBackingLayers > 0 ? backingFilament : null,
    totalLayerCount,
    totalHeightMm,
  };
}
