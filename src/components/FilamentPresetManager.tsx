/**
 * CRUD UI for managing saved filament presets (localStorage)
 */
import React, { useState, useRef } from 'react';
import { Save, Trash2, Upload, Download, Edit2, Check, X } from 'lucide-react';
import type { FilamentColorConfig } from '../api/types';
import type { SavedPreset } from '../hooks/useFilamentStorage';

interface FilamentPresetManagerProps {
  presets: SavedPreset[];
  currentColors: FilamentColorConfig[];
  isConfigValid: boolean;
  onLoadPreset: (colors: FilamentColorConfig[]) => void;
  onSavePreset: (name: string, colors: FilamentColorConfig[]) => SavedPreset;
  onUpdatePreset: (id: string, name: string, colors: FilamentColorConfig[]) => void;
  onDeletePreset: (id: string) => void;
  onRenamePreset: (id: string, name: string) => void;
  onExportPresets: () => string;
  onImportPresets: (json: string) => { imported: number; errors: string[] };
  disabled?: boolean;
}

export const FilamentPresetManager: React.FC<FilamentPresetManagerProps> = ({
  presets,
  currentColors,
  isConfigValid,
  onLoadPreset,
  onSavePreset,
  onUpdatePreset,
  onDeletePreset,
  onRenamePreset,
  onExportPresets,
  onImportPresets,
  disabled = false,
}) => {
  const [saveName, setSaveName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [importMessageType, setImportMessageType] = useState<'success' | 'error'>('success');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSave = () => {
    const trimmed = saveName.trim();
    if (!trimmed || !isConfigValid) return;
    onSavePreset(trimmed, currentColors);
    setSaveName('');
  };

  const handleSaveKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave();
  };

  const handleStartRename = (preset: SavedPreset) => {
    setEditingId(preset.id);
    setEditName(preset.name);
  };

  const handleConfirmRename = () => {
    if (editingId && editName.trim()) {
      onRenamePreset(editingId, editName.trim());
    }
    setEditingId(null);
    setEditName('');
  };

  const handleCancelRename = () => {
    setEditingId(null);
    setEditName('');
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleConfirmRename();
    if (e.key === 'Escape') handleCancelRename();
  };

  const handleExport = () => {
    try {
      const json = onExportPresets();
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'filament-presets.json';
      a.click();
      // Delay revocation to allow Firefox time to start download
      setTimeout(() => URL.revokeObjectURL(url), 100);
    } catch (err) {
      setImportMessage('Failed to export presets');
      setTimeout(() => setImportMessage(null), 4000);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const maxFileSize = 1024 * 1024; // 1MB
    if (file.size > maxFileSize) {
      setImportMessage('File too large (max 1MB)');
      setImportMessageType('error');
      setTimeout(() => setImportMessage(null), 4000);
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const result = onImportPresets(text);
      if (result.errors.length > 0) {
        setImportMessage(`Imported ${result.imported} preset(s). Errors: ${result.errors.join(', ')}`);
        setImportMessageType('error');
      } else {
        setImportMessage(`Imported ${result.imported} preset(s) successfully`);
        setImportMessageType('success');
      }
      setTimeout(() => setImportMessage(null), 4000);
    };
    reader.onerror = () => {
      setImportMessage('Failed to read file');
      setImportMessageType('error');
      setTimeout(() => setImportMessage(null), 4000);
    };
    reader.readAsText(file);

    // Reset input so same file can be re-imported
    e.target.value = '';
  };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-700">Saved Presets</h4>

      {/* Save current config */}
      <div className="flex gap-2">
        <input
          type="text"
          value={saveName}
          onChange={e => setSaveName(e.target.value)}
          onKeyDown={handleSaveKeyDown}
          placeholder="Preset name..."
          disabled={disabled || !isConfigValid}
          className="flex-1 text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-purple-400 disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSave}
          disabled={disabled || !isConfigValid || !saveName.trim()}
          className="flex items-center gap-1 text-sm px-3 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <Save className="w-3.5 h-3.5" />
          Save
        </button>
      </div>

      {/* Preset list */}
      {presets.length > 0 && (
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {presets.map(preset => (
            <div
              key={preset.id}
              className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-100 group"
            >
              {editingId === preset.id ? (
                <>
                  <input
                    type="text"
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={handleRenameKeyDown}
                    autoFocus
                    className="flex-1 text-sm border border-purple-300 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
                  />
                  <button
                    onClick={handleConfirmRename}
                    className="text-green-600 hover:text-green-800 p-0.5"
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={handleCancelRename}
                    className="text-gray-400 hover:text-gray-600 p-0.5"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </>
              ) : (
                <>
                  {/* Color swatches */}
                  <div className="flex gap-0.5">
                    {preset.colors.slice(0, 6).map((c, i) => (
                      <span
                        key={i}
                        className="w-3 h-3 rounded-sm border border-gray-200"
                        style={{ backgroundColor: c.hex }}
                      />
                    ))}
                    {preset.colors.length > 6 && (
                      <span className="text-[10px] text-gray-400">+{preset.colors.length - 6}</span>
                    )}
                  </div>

                  {/* Name + load */}
                  <button
                    onClick={() => onLoadPreset(preset.colors)}
                    disabled={disabled}
                    className="flex-1 text-left text-sm text-gray-700 hover:text-purple-700 truncate disabled:cursor-not-allowed"
                    title={`Load "${preset.name}" (${preset.colors.length} colors)`}
                  >
                    {preset.name}
                  </button>

                  {/* Color count */}
                  <span className="text-[10px] text-gray-400">{preset.colors.length}c</span>

                  {/* Overwrite */}
                  <button
                    onClick={() => onUpdatePreset(preset.id, preset.name, currentColors)}
                    disabled={disabled || !isConfigValid}
                    className="opacity-0 group-hover:opacity-100 text-blue-500 hover:text-blue-700 disabled:text-gray-300 p-0.5 transition-opacity"
                    title="Overwrite with current config"
                  >
                    <Save className="w-3 h-3" />
                  </button>

                  {/* Rename */}
                  <button
                    onClick={() => handleStartRename(preset)}
                    disabled={disabled}
                    className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600 disabled:text-gray-300 p-0.5 transition-opacity"
                    title="Rename"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => onDeletePreset(preset.id)}
                    disabled={disabled}
                    className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 disabled:text-gray-300 p-0.5 transition-opacity"
                    title="Delete"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {presets.length === 0 && (
        <p className="text-xs text-gray-400 italic">No saved presets yet</p>
      )}

      {/* Import / Export */}
      <div className="flex gap-2 pt-1 border-t border-gray-200">
        <button
          onClick={handleExport}
          disabled={disabled || presets.length === 0}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 disabled:text-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <Download className="w-3 h-3" />
          Export
        </button>
        <button
          onClick={handleImportClick}
          disabled={disabled}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 disabled:text-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <Upload className="w-3 h-3" />
          Import
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleImportFile}
          className="hidden"
        />
      </div>

      {/* Import feedback */}
      {importMessage && (
        <p className={`text-xs ${importMessageType === 'success' ? 'text-green-600' : 'text-red-600'}`}>
          {importMessage}
        </p>
      )}
    </div>
  );
};

export default FilamentPresetManager;
