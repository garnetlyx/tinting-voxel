import React, { useId } from 'react';

interface RangeFieldProps {
  label: string;
  /** Formatted value shown beside the label. */
  display: string;
  value: number;
  min: number;
  max: number;
  step?: number | 'any';
  onChange: (value: number) => void;
  hint?: React.ReactNode;
  disabled?: boolean;
}

/** A slider named by its label; the formatted value shows in mono and is its aria-valuetext. */
export const RangeField: React.FC<RangeFieldProps> = ({
  label, display, value, min, max, step = 1, onChange, hint, disabled = false,
}) => {
  const id = useId();
  const fill = max > min ? Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100)) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-ink-soft">{label}</label>
        <span className="tv-value shrink-0" aria-hidden="true">{display}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={display}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="tv-range mt-1 block"
        style={{ '--fill': `${fill}%` } as React.CSSProperties}
      />
      {hint && <p className="tv-help">{hint}</p>}
    </div>
  );
};
