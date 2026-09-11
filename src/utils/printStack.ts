import type { PrintStackInfo } from '../api/types';

export function buildPrintStack(
  layerCount: number,
  layerHeight: number,
  whiteBackingLayers: number,
): PrintStackInfo {
  const opticalLayerCount = layerCount;
  const totalLayerCount = opticalLayerCount + whiteBackingLayers;
  const totalHeightMm = Math.round(totalLayerCount * layerHeight * 100) / 100;

  return {
    opticalLayerCount,
    whiteBackingLayers,
    totalLayerCount,
    totalHeightMm,
  };
}
