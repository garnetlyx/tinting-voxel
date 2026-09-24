import { useTranslation } from '../i18n';
/**
 * Mode selector component for switching between Pixel and SVG processing modes
 */
import React from 'react';
import { Grid3x3, Spline } from 'lucide-react';
import type { ProcessingMode } from '../api/types';

interface ModeSelectorProps {
  mode: ProcessingMode;
  onModeChange: (mode: ProcessingMode) => void;
  disabled?: boolean;
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({
  mode,
  onModeChange,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const options = [
    { value: 'pixel' as const, label: t('parameters:pixel'), description: t('parameters:bestForPixelArtFineDetails'), Icon: Grid3x3 },
    { value: 'svg' as const, label: 'SVG', description: t('parameters:bestForLogosSimpleShapes'), Icon: Spline },
  ];
  return (
    <div role="group" aria-label={t('parameters:processingMode')} className="grid grid-cols-2 gap-2">
      {options.map(({ value, label, description, Icon }) => (
        <button
          key={value}
          type="button"
          aria-pressed={mode === value}
          onClick={() => onModeChange(value)}
          disabled={disabled}
          className="rounded-sheet border border-rule-strong bg-paper-raised px-3 py-2.5 text-left text-ink transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-50 aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-paper-raised"
        >
          <span className="flex items-center gap-1.5 text-sm font-semibold">
            <Icon className="h-4 w-4" aria-hidden="true" />{label}
          </span>
          <span className="mt-1 block text-xs leading-4 opacity-75">{description}</span>
        </button>
      ))}
    </div>
  );
};
