/**
 * Error message display component
 */
import React from 'react';

interface ErrorMessageProps {
  message: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ message }) => {
  return (
    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
      <p className="text-red-600 text-sm">{message}</p>
    </div>
  );
};
