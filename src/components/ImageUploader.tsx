import { useTranslation } from '../i18n';
/**
 * Image upload component with drag-and-drop support
 */
import React, { useRef, useState, useCallback } from 'react';
import { Upload } from 'lucide-react';
import { OverprintMark } from './OverprintMark';

interface ImageUploaderProps {
  onImageUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFileDrop?: (file: File) => void;
  /** A slim bar once an image is loaded; the full drop area otherwise. */
  compact?: boolean;
}

export const ImageUploader: React.FC<ImageUploaderProps> = ({ onImageUpload, onFileDrop, compact = false }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file && onFileDrop) {
      onFileDrop(file);
    }
  }, [onFileDrop]);

  const label = isDragging ? t('editor:dropImageHere') : t('editor:clickOrDragImageHere');
  const dropState = isDragging
    ? 'border-magenta bg-magenta/5'
    : 'border-rule-strong hover:border-ink hover:bg-paper-sunk/60';

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp,image/bmp,image/svg+xml,.svg"
        onChange={onImageUpload}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={compact
          ? `flex w-full items-center gap-3 rounded-sheet border border-dashed px-4 py-3 text-left transition-colors ${dropState}`
          : `group flex w-full flex-col items-center justify-center gap-4 rounded-sheet border-2 border-dashed px-6 py-12 transition-colors sm:py-16 ${dropState}`}
      >
        {compact ? (
          <>
            <Upload className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="text-sm font-semibold">{label}</span>
            <span className="ml-auto hidden font-mono text-xs text-ink-muted sm:inline">PNG, JPEG, GIF, WebP, BMP, SVG</span>
          </>
        ) : (
          <>
            <OverprintMark className={`h-24 w-24 transition-transform duration-300 sm:h-28 sm:w-28 ${isDragging ? 'scale-110' : 'group-hover:scale-105'}`} />
            <span className="flex items-center gap-2 text-base font-semibold text-ink">
              <Upload className={`h-4 w-4 ${isDragging ? 'animate-bounce' : ''}`} aria-hidden="true" />
              {label}
            </span>
            <span className="font-mono text-xs text-ink-muted">PNG, JPEG, GIF, WebP, BMP, SVG</span>
          </>
        )}
      </button>
    </div>
  );
};
