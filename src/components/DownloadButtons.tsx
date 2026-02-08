/**
 * Download buttons component (CSV, STL, 3MF, and Print Settings)
 */
import React from 'react';
import { Download, Settings } from 'lucide-react';

interface DownloadButtonsProps {
  colorCount: number;
  onDownloadCSV: () => void;
  onDownloadSTL: () => void;
  onDownload3MF?: () => void;
  onDownloadPrintSettings?: () => void;
  processing: boolean;
  showCSV?: boolean;
}

export const DownloadButtons: React.FC<DownloadButtonsProps> = ({
  colorCount,
  onDownloadCSV,
  onDownloadSTL,
  onDownload3MF,
  onDownloadPrintSettings,
  processing,
  showCSV = true,
}) => {
  return (
    <div className="flex items-center justify-between mb-6">
      <h2 className="text-xl font-semibold text-gray-800">
        Extracted Colors ({colorCount})
      </h2>
      <div className="flex gap-3 flex-wrap justify-end">
        {showCSV && (
          <button
            onClick={onDownloadCSV}
            disabled={processing}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 disabled:bg-gray-400"
          >
            <Download className="w-4 h-4" />
            Download CSV
          </button>
        )}
        <button
          onClick={onDownloadSTL}
          disabled={processing}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:bg-gray-400"
        >
          <Download className="w-4 h-4" />
          {processing ? 'Generating...' : 'Download STL (ZIP)'}
        </button>
        {onDownload3MF && (
          <button
            onClick={onDownload3MF}
            disabled={processing}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:bg-gray-400"
          >
            <Download className="w-4 h-4" />
            {processing ? 'Generating...' : 'Download 3MF'}
          </button>
        )}
        {onDownloadPrintSettings && (
          <button
            onClick={onDownloadPrintSettings}
            disabled={processing}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors flex items-center gap-2 disabled:bg-gray-400"
          >
            <Settings className="w-4 h-4" />
            Print Settings
          </button>
        )}
      </div>
    </div>
  );
};
