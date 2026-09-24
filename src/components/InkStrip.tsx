import React from 'react';
import type { FilamentColorConfig } from '../api/types';
import { filamentLabel } from '../utils/filaments';

interface InkStripProps {
  colors: FilamentColorConfig[];
  className?: string;
}

/**
 * The current filament set as a press's ink units: one swatch per filament,
 * lettered with its code. Decorative; the settings rail lists the same set.
 */
export const InkStrip: React.FC<InkStripProps> = ({ colors, className = '' }) => (
  <div aria-hidden="true" className={`flex items-end gap-px ${className}`}>
    {colors.map((color, index) => (
      <div key={index} className="flex flex-col items-center gap-0.5" title={color.name}>
        <span className="block h-4 w-4 border border-ink/60" style={{ backgroundColor: color.hex }} />
        <span className="font-mono text-[10px] leading-none text-ink-muted">{filamentLabel(color)}</span>
      </div>
    ))}
  </div>
);
