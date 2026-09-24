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
    <div className="mb-6 p-4 bg-gray-50 rounded-lg space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
          <Crop className="w-4 h-4" />{t('editor:imageEditor')}</h3>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            disabled={disabled || !hasEdits}
            className="flex items-center gap-1 text-xs px-2 py-1 text-gray-500 hover:text-gray-700 disabled:text-gray-300 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />{t('common:reset')}</button>
          <button
            onClick={onCancel}
            disabled={disabled}
            className="text-xs px-3 py-1 text-gray-500 hover:text-gray-700 border border-gray-300 rounded transition-colors"
          >{t('common:cancel')}</button>
          <button
            onClick={handleApply}
            disabled={disabled}
            className="flex items-center gap-1 text-xs px-3 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:bg-gray-300 transition-colors"
          >
            <Check className="w-3 h-3" />{t('editor:applyProcess')}</button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <Maximize2 className="w-3.5 h-3.5 text-gray-500" />
          <label className="text-gray-600">{t('editor:resize')}</label>
          <input
            type="range"
            min="10"
            max="100"
            value={resizePercent}
            onChange={(e) => setResizePercent(parseInt(e.target.value))}
            disabled={disabled}
            className="w-24"
          />
          <span className="text-gray-700 w-10 text-right">{resizePercent}%</span>
        </div>

        <span className="text-gray-300">|</span>

        <button
          onClick={() => {
            setIsCropping(!isCropping);
            if (isCropping) setCropRegion(null);
          }}
          disabled={disabled}
          className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors ${
            isCropping
              ? 'bg-purple-100 text-purple-700 border border-purple-300'
              : 'text-gray-600 hover:bg-gray-200 border border-transparent'
          }`}
        >
          <Crop className="w-3 h-3" />
          {isCropping ? t('editor:cropping') : t('editor:crop')}
        </button>

        <span className="text-xs text-gray-400 ml-auto">
          {effectiveWidth} x {effectiveHeight} px
          {cropRegion && isCropping && (
            <> → {Math.round(cropRegion.width * image.width / effectiveWidth)} x {Math.round(cropRegion.height * image.height / effectiveHeight)} px</>
          )}
        </span>
      </div>

      {/* Canvas */}
      <div
        ref={containerRef}
        className="flex justify-center bg-white rounded border border-gray-200 p-2 overflow-hidden"
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
        <p className="text-xs text-gray-400 text-center">{t('editor:clickAndDragOnTheImageToSelectA')}</p>
      )}
    </div>
  );
};
