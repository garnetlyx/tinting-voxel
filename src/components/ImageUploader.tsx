/**
 * Image upload component with drag-and-drop support
 */
import React, { useRef, useState, useCallback } from 'react';
import { Upload } from 'lucide-react';

interface ImageUploaderProps {
  onImageUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFileDrop?: (file: File) => void;
}

export const ImageUploader: React.FC<ImageUploaderProps> = ({ onImageUpload, onFileDrop }) => {
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

  return (
    <div className="mb-8">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp,image/bmp"
        onChange={onImageUpload}
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`w-full py-8 border-2 border-dashed rounded-xl transition-all flex flex-col items-center justify-center gap-2 ${
          isDragging
            ? 'border-purple-500 bg-purple-100 text-purple-600 scale-[1.02]'
            : 'border-gray-300 hover:border-purple-400 hover:bg-purple-50 text-gray-600 hover:text-purple-600'
        }`}
      >
        <Upload className={`w-8 h-8 ${isDragging ? 'animate-bounce' : ''}`} />
        <span className="font-medium">
          {isDragging ? 'Drop image here' : 'Click or drag image here'}
        </span>
        <span className="text-xs text-gray-400">PNG, JPEG, GIF, WebP, BMP</span>
      </button>
    </div>
  );
};
