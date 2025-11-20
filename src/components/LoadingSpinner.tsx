/**
 * Loading spinner component
 */
import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message = 'Processing...' }) => {
  return (
    <div className="text-center py-12">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mx-auto mb-4"></div>
      <p className="text-gray-600">{message}</p>
    </div>
  );
};
