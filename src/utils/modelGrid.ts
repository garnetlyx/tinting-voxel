/**
 * Model grid resolution policy, mirroring backend image_processor.model_pitch.
 * Limits come from /api/v2/filament-presets, so an upload resampled here is
 * already at the grid the backend processes.
 */
export interface ModelGridLimits {
  maxCells: number;
  maxSidePx: number;
}

export interface GridSize {
  width: number;
  height: number;
}

/**
 * Model pitch in mm for a width x height image at pixelSize mm per pixel.
 * Images within the limits keep their pixel grid; when resampling, a pitch
 * between half and one detail width becomes one detail width.
 */
export function modelPitch(
  width: number,
  height: number,
  pixelSize: number,
  detailSize: number | null,
  limits: ModelGridLimits,
): number {
  let pitch = Math.max(
    pixelSize,
    pixelSize * Math.sqrt((width * height) / limits.maxCells),
    (pixelSize * Math.max(width, height)) / limits.maxSidePx,
  );
  if (detailSize && pitch > pixelSize && detailSize / 2 < pitch && pitch < detailSize) {
    pitch = detailSize;
  }
  return pitch;
}

/** Grid size at that pitch; sides round down so the pitch never falls below it. */
export function modelGridSize(width: number, height: number, pixelSize: number, pitch: number): GridSize {
  if (pitch <= pixelSize) return { width, height };
  const scale = pixelSize / pitch;
  return { width: Math.max(1, Math.floor(width * scale)), height: Math.max(1, Math.floor(height * scale)) };
}
