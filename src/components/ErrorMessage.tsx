import { useLocalizedMessage } from '../i18n/messages';
/**
 * Error message display component
 */
import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface ErrorMessageProps {
  message: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ message }) => {
  const localize = useLocalizedMessage();
  return (
    <div role="alert" className="flex items-start gap-3 rounded-sheet border border-signal-error/30 border-l-4 border-l-signal-error bg-signal-error/5 px-4 py-3">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-signal-error" aria-hidden="true" />
      <p className="text-sm text-signal-error">{localize(message)}</p>
    </div>
  );
};
