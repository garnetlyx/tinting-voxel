import React from 'react';

interface OverprintMarkProps {
  className?: string;
  /** Let the inks drift in and out of register. */
  animated?: boolean;
}

/**
 * Cyan, magenta and yellow discs overprinted with multiply blending: where
 * they overlap, the colors mix the way stacked translucent filament does.
 */
export const OverprintMark: React.FC<OverprintMarkProps> = ({ className = '', animated = true }) => (
  <svg
    viewBox="0 0 120 120"
    aria-hidden="true"
    focusable="false"
    className={`${animated ? 'tv-drift' : ''} ${className}`}
    style={{ isolation: 'isolate', overflow: 'visible' }}
  >
    <circle className="tv-ink tv-ink-c" cx="46" cy="47" r="31" style={{ fill: 'rgb(var(--cyan))' }} />
    <circle className="tv-ink tv-ink-m" cx="74" cy="47" r="31" style={{ fill: 'rgb(var(--magenta))' }} />
    <circle className="tv-ink tv-ink-y" cx="60" cy="72" r="31" style={{ fill: 'rgb(var(--yellow))' }} />
  </svg>
);
