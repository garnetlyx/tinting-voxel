import type { BackingMode, PrintStackInfo } from '../api/types';

export function buildPrintStack(
  layerCount: number,
  layerHeight: number,
  whiteBackingLayers: number,
  backingMode: BackingMode = 'white',
): PrintStackInfo {
  const opticalLayerCount = layerCount;
  const totalLayerCount = opticalLayerCount + whiteBackingLayers;
  const totalHeightMm = Math.round(totalLayerCount * layerHeight * 100) / 100;

  return {
    opticalLayerCount,
    whiteBackingLayers,
    backingMode,
    totalLayerCount,
    totalHeightMm,
  };
}
