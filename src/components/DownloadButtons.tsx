/**
 * Download buttons component (CSV and STL)
 */
import React from 'react';
import { Download } from 'lucide-react';

interface DownloadButtonsProps {
  colorCount: number;
  onDownloadCSV: () => void;
  onDownloadSTL: () => void;
  processing: boolean;
}

export const DownloadButtons: React.FC<DownloadButtonsProps> = ({
  colorCount,
  onDownloadCSV,
  onDownloadSTL,
  processing,
}) => {
  return (
    <div className="flex items-center justify-between mb-6">
      <h2 className="text-xl font-semibold text-gray-800">
        Extracted Colors ({colorCount})
      </h2>
      <div className="flex gap-3">
        <button
          onClick={onDownloadCSV}
          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          Download CSV
        </button>
        <button
          onClick={onDownloadSTL}
          disabled={processing}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:bg-gray-400"
        >
          <Download className="w-4 h-4" />
          {processing ? 'Generating...' : 'Download All STLs (ZIP)'}
        </button>
      </div>
    </div>
  );
};
