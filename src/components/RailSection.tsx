import React, { useId } from 'react';

interface RailSectionProps {
  /** Position in the settings rail, printed as a two-digit number. */
  index: number;
  title: string;
  children: React.ReactNode;
}

/** A numbered group of settings in the side rail. */
export const RailSection: React.FC<RailSectionProps> = ({ index, title, children }) => {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className="tv-rise border-t-2 border-ink pt-3"
      style={{ '--i': index } as React.CSSProperties}
    >
      <div className="mb-4 flex items-baseline gap-3">
        <span className="font-mono text-xs text-ink-muted" aria-hidden="true">{String(index).padStart(2, '0')}</span>
        <h2 id={id} className="tv-kicker !text-ink">{title}</h2>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
  );
};
