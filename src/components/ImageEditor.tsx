import { useTranslation } from '../i18n';
/**
 * Image pre-processing component for crop and resize before color processing.
 * Uses canvas-based rendering with click-and-drag crop selection.
 */
import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Crop, Maximize2, RotateCcw, Check } from 'lucide-react';

interface CropRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ImageEditorProps {
  image: HTMLImageElement;
  /** Longest output side; processing never uses more, and larger canvases can fail on phones. */
  maxSidePx: number;
  onApply: (editedImage: HTMLImageElement) => void;
  onCancel: () => void;
  disabled?: boolean;
}

export const ImageEditor: React.FC<ImageEditorProps> = ({
  image,
  maxSidePx,
  onApply,
  onCancel,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Scale factor for display (image may be larger than canvas)
  const [displayScale, setDisplayScale] = useState(1);

  // Resize: percentage of original
  const [resizePercent, setResizePercent] = useState(100);

  // Crop state
  const [isCropping, setIsCropping] = useState(false);
  const [cropRegion, setCropRegion] = useState<CropRegion | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Compute effective dimensions after resize
  const effectiveWidth = Math.round(image.width * resizePercent / 100);
  const effectiveHeight = Math.round(image.height * resizePercent / 100);

  // Draw the image on canvas with crop overlay
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const maxW = 600;
    const maxH = 400;
    const scale = Math.min(maxW / effectiveWidth, maxH / effectiveHeight, 1);
    setDisplayScale(scale);

    canvas.width = Math.round(effectiveWidth * scale);
    canvas.height = Math.round(effectiveHeight * scale);

    // Draw resized image
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

    // Draw crop overlay
    if (cropRegion && isCropping) {
      // Dim outside crop region
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Clear crop region
      const cx = Math.round(cropRegion.x * scale);
      const cy = Math.round(cropRegion.y * scale);
      const cw = Math.round(cropRegion.width * scale);
      const ch = Math.round(cropRegion.height * scale);

      ctx.clearRect(cx, cy, cw, ch);
      ctx.drawImage(
        image,
        cropRegion.x * image.width / effectiveWidth,
        cropRegion.y * image.height / effectiveHeight,
        cropRegion.width * image.width / effectiveWidth,
        cropRegion.height * image.height / effectiveHeight,
        cx, cy, cw, ch
      );

      // Crop border
      ctx.strokeStyle = '#7c3aed';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(cx, cy, cw, ch);
      ctx.setLineDash([]);

      // Dimension label
      const cropW = Math.round(cropRegion.width * image.width / effectiveWidth);
      const cropH = Math.round(cropRegion.height * image.height / effectiveHeight);
      ctx.fillStyle = 'rgba(124, 58, 237, 0.85)';
      ctx.fillRect(cx, cy - 20, 100, 18);
      ctx.fillStyle = '#fff';
      ctx.font = '11px sans-serif';
      ctx.fillText(`${cropW} x ${cropH} px`, cx + 4, cy - 6);
    }
  }, [image, effectiveWidth, effectiveHeight, cropRegion, isCropping]);

  useEffect(() => {
    draw();
  }, [draw]);

  // Mouse and touch handlers for crop selection
  const getCanvasPos = (e: React.MouseEvent | React.TouchEvent): { x: number; y: number } => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();

    // Get client coordinates from mouse or touch event
    let clientX: number, clientY: number;
    if ('touches' in e && e.touches.length > 0) {
      // Touch event
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else if ('clientX' in e) {
      // Mouse event
      clientX = e.clientX;
      clientY = e.clientY;
    } else {
      return { x: 0, y: 0 };
    }

    return {
      x: (clientX - rect.left) / displayScale,
      y: (clientY - rect.top) / displayScale,
    };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!isCropping || disabled) return;
    const pos = getCanvasPos(e);
    setDragStart(pos);
    setIsDragging(true);
    setCropRegion(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !dragStart || disabled) return;
    const pos = getCanvasPos(e);
    const x = Math.max(0, Math.min(dragStart.x, pos.x));
    const y = Math.max(0, Math.min(dragStart.y, pos.y));
    const width = Math.min(Math.abs(pos.x - dragStart.x), effectiveWidth - x);
    const height = Math.min(Math.abs(pos.y - dragStart.y), effectiveHeight - y);

    if (width > 5 && height > 5) {
      setCropRegion({ x, y, width, height });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragStart(null);
  };

  // Touch event handlers
  const handleTouchStart = (e: React.TouchEvent) => {
    if (!isCropping || disabled) return;
    e.preventDefault(); // Prevent scrolling while cropping
    const pos = getCanvasPos(e);
    setDragStart(pos);
    setIsDragging(true);
    setCropRegion(null);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!isDragging || !dragStart || disabled) return;
    e.preventDefault(); // Prevent scrolling while dragging
    const pos = getCanvasPos(e);
    const x = Math.max(0, Math.min(dragStart.x, pos.x));
    const y = Math.max(0, Math.min(dragStart.y, pos.y));
    const width = Math.min(Math.abs(pos.x - dragStart.x), effectiveWidth - x);
    const height = Math.min(Math.abs(pos.y - dragStart.y), effectiveHeight - y);

    if (width > 5 && height > 5) {
      setCropRegion({ x, y, width, height });
    }
  };

  const handleTouchEnd = () => {
    setIsDragging(false);
    setDragStart(null);
  };

  // Reset all edits
  const handleReset = () => {
    setResizePercent(100);
    setCropRegion(null);
    setIsCropping(false);
  };

  // Apply edits and create new HTMLImageElement
  const handleApply = () => {
    const canvas = document.createElement('canvas');
    const setOutputSize = (width: number, height: number) => {
      const scale = Math.min(1, maxSidePx / Math.max(width, height));
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
    };

    if (cropRegion && isCropping) {
      // Apply crop on the resized image coordinates, mapping back to original
      const srcX = cropRegion.x * image.width / effectiveWidth;
      const srcY = cropRegion.y * image.height / effectiveHeight;
      const srcW = cropRegion.width * image.width / effectiveWidth;
      const srcH = cropRegion.height * image.height / effectiveHeight;

      setOutputSize(srcW, srcH);
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(image, srcX, srcY, srcW, srcH, 0, 0, canvas.width, canvas.height);
      }
    } else if (resizePercent !== 100) {
      // Apply resize only
      setOutputSize(effectiveWidth, effectiveHeight);
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      }
    } else {
      // No edits, pass through original
      onApply(image);
      return;
    }

    const newImg = new Image();
    newImg.onload = () => onApply(newImg);
    newImg.onerror = () => {
      console.error('ImageEditor: Failed to load edited image from canvas data URL');
      // Fallback to original image on error
      onApply(image);
    };
    newImg.src = canvas.toDataURL('image/png');
  };

  const hasEdits = resizePercent !== 100 || (isCropping && cropRegion !== null);

  return (
    <section className="space-y-4 rounded-sheet border border-rule bg-paper p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="tv-heading flex items-center gap-2">
          <Crop className="h-4 w-4" aria-hidden="true" />{t('editor:imageEditor')}</h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleReset}
            disabled={disabled || !hasEdits}
            className="tv-btn-ghost tv-btn-sm"
          >
            <RotateCcw className="h-3 w-3" aria-hidden="true" />{t('common:reset')}</button>
          <button
            onClick={onCancel}
            disabled={disabled}
            className="tv-btn-outline tv-btn-sm"
          >{t('common:cancel')}</button>
          <button
            onClick={handleApply}
            disabled={disabled}
            className="tv-btn-primary tv-btn-sm !px-3"
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />{t('editor:applyProcess')}</button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <div className="flex items-center gap-2">
          <Maximize2 className="h-3.5 w-3.5 text-ink-muted" aria-hidden="true" />
          <label htmlFor="image-resize" className="text-ink-soft">{t('editor:resize')}</label>
          <input
            id="image-resize"
            type="range"
            min="10"
            max="100"
            value={resizePercent}
            onChange={(e) => setResizePercent(parseInt(e.target.value))}
            disabled={disabled}
            className="tv-range w-28"
            style={{ '--fill': `${((resizePercent - 10) / 90) * 100}%` } as React.CSSProperties}
          />
          <span className="tv-value w-10 text-right">{resizePercent}%</span>
        </div>

        <span className="hidden h-4 w-px bg-rule-strong sm:block" aria-hidden="true" />

        <button
          onClick={() => {
            setIsCropping(!isCropping);
            if (isCropping) setCropRegion(null);
          }}
          disabled={disabled}
          aria-pressed={isCropping}
          className="tv-btn-outline tv-btn-sm aria-pressed:bg-ink aria-pressed:text-paper-raised"
        >
          <Crop className="h-3 w-3" aria-hidden="true" />
          {isCropping ? t('editor:cropping') : t('editor:crop')}
        </button>

        <span className="ml-auto font-mono text-xs text-ink-muted">
          {effectiveWidth} x {effectiveHeight} px
          {cropRegion && isCropping && (
            <> → {Math.round(cropRegion.width * image.width / effectiveWidth)} x {Math.round(cropRegion.height * image.height / effectiveHeight)} px</>
          )}
        </span>
      </div>

      {/* Canvas */}
      <div
        ref={containerRef}
        className="flex justify-center overflow-hidden rounded-sheet border border-rule bg-paper-raised p-2"
      >
        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          onTouchCancel={handleTouchEnd}
          className={isCropping ? 'cursor-crosshair' : 'cursor-default'}
          style={{ maxWidth: '100%', touchAction: isCropping ? 'none' : 'auto' }}
        />
      </div>

      {isCropping && !cropRegion && (
        <p className="tv-help text-center">{t('editor:clickAndDragOnTheImageToSelectA')}</p>
      )}
    </section>
  );
};
