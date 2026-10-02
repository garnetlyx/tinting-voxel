/**
 * Rasterize an uploaded SVG so it can enter the editor like any other image.
 * Processing always works on pixels; a vector source is drawn once at a
 * generous size so neither mode inherits a blurry upscale.
 */

/** Longest side of the raster drawn from an SVG source. */
export const SVG_RASTER_SIDE_PX = 2048;

/** Browsers size an SVG with no width, height, or viewBox at 300x150. */
const DEFAULT_SVG_SIZE = { width: 300, height: 150 };

const PX_PER_UNIT: Record<string, number> = {
  '': 1, px: 1, pt: 96 / 72, pc: 16, in: 96, cm: 96 / 2.54, mm: 96 / 25.4,
};

export interface Size {
  width: number;
  height: number;
}

export function isSvgFile(file: File): boolean {
  return file.type === 'image/svg+xml' || (file.type === '' && /\.svg$/i.test(file.name));
}

/** An absolute SVG length in px, or null for relative or invalid values. */
function lengthPx(value: string | null): number | null {
  const match = value?.trim().match(/^([+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)(px|pt|pc|in|cm|mm)?$/i);
  if (!match) return null;
  const px = parseFloat(match[1]) * PX_PER_UNIT[(match[2] ?? '').toLowerCase()];
  return px > 0 && Number.isFinite(px) ? px : null;
}

function viewBoxSize(value: string | null): Size | null {
  const parts = value?.trim().split(/[\s,]+/).map(Number);
  if (!parts || parts.length !== 4 || parts.some(n => !Number.isFinite(n))) return null;
  const [, , width, height] = parts;
  return width > 0 && height > 0 ? { width, height } : null;
}

/** The size a browser would give the SVG, used for its aspect ratio. */
export function svgIntrinsicSize(svg: Element): Size {
  const width = lengthPx(svg.getAttribute('width'));
  const height = lengthPx(svg.getAttribute('height'));
  const viewBox = viewBoxSize(svg.getAttribute('viewBox'));
  if (width && height) return { width, height };
  if (viewBox && width) return { width, height: width * viewBox.height / viewBox.width };
  if (viewBox && height) return { width: height * viewBox.width / viewBox.height, height };
  if (viewBox) return viewBox;
  return { width: width ?? DEFAULT_SVG_SIZE.width, height: height ?? DEFAULT_SVG_SIZE.height };
}

/** Scale a size so its longest side is exactly `longestSide`. */
export function rasterSize(size: Size, longestSide: number): Size {
  const scale = longestSide / Math.max(size.width, size.height);
  return {
    width: Math.max(1, Math.round(size.width * scale)),
    height: Math.max(1, Math.round(size.height * scale)),
  };
}

/**
 * Give the SVG explicit pixel dimensions. Without them some browsers report a
 * zero or default natural size, and canvas draws nothing or a blurry thumbnail.
 */
export function sizeSvgMarkup(markup: string, longestSide: number): { markup: string; size: Size } {
  const doc = new DOMParser().parseFromString(markup, 'image/svg+xml');
  const svg = doc.documentElement;
  if (doc.getElementsByTagName('parsererror').length > 0 || svg.localName !== 'svg') {
    throw new Error('Not a valid SVG document');
  }
  const intrinsic = svgIntrinsicSize(svg);
  // Without a viewBox, new width/height would only widen the viewport.
  if (!viewBoxSize(svg.getAttribute('viewBox'))) {
    svg.setAttribute('viewBox', `0 0 ${intrinsic.width} ${intrinsic.height}`);
  }
  const size = rasterSize(intrinsic, longestSide);
  svg.setAttribute('width', String(size.width));
  svg.setAttribute('height', String(size.height));
  return { markup: new XMLSerializer().serializeToString(doc), size };
}

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = src;
  });
}

/** Draw an SVG file to a PNG-backed image whose longest side is `longestSide`. */
export async function rasterizeSvg(file: File, longestSide: number = SVG_RASTER_SIDE_PX): Promise<HTMLImageElement> {
  const { markup, size } = sizeSvgMarkup(await readText(file), longestSide);
  // An SVG loaded as an <img> runs no scripts and fetches no external resources.
  const svgImage = await loadImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`);

  const canvas = document.createElement('canvas');
  canvas.width = size.width;
  canvas.height = size.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Failed to get 2D canvas context');
  ctx.drawImage(svgImage, 0, 0, size.width, size.height);
  return loadImage(canvas.toDataURL('image/png'));
}
