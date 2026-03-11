import type { PrintStackInfo } from '../api/types';

export function buildPrintStack(
  layerCount: number,
  layerHeight: number,
  whiteBackingLayers: number,
  basePlateThickness: number,
  doubleSided: boolean,
): PrintStackInfo {
  const opticalLayerCount = layerCount * (doubleSided ? 2 : 1);
  const totalLayerCount = opticalLayerCount + whiteBackingLayers;
  const totalHeightMm = Math.round((totalLayerCount * layerHeight + basePlateThickness) * 100) / 100;

  return {
    opticalLayerCount,
    whiteBackingLayers,
    totalLayerCount,
    totalHeightMm,
  };
}
