import { useLocalizedMessage } from '../i18n/messages';
import { useTranslation } from '../i18n';
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
  const { t } = useTranslation();
  const localize = useLocalizedMessage();
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
      <h3 className="text-sm font-semibold text-ink">{t('filaments:savedPresets')}</h3>

      {/* Save current config */}
      <div className="flex gap-2">
        <input
          type="text"
          value={saveName}
          onChange={e => setSaveName(e.target.value)}
          onKeyDown={handleSaveKeyDown}
          placeholder={t('filaments:presetName')}
          disabled={disabled || !isConfigValid}
          className="tv-input min-w-0 flex-1 !py-1.5"
        />
        <button
          onClick={handleSave}
          disabled={disabled || !isConfigValid || !saveName.trim()}
          className="tv-btn-primary tv-btn-sm !px-3"
        >
          <Save className="h-3.5 w-3.5" aria-hidden="true" />{t('common:save')}</button>
      </div>

      {/* Preset list */}
      {presets.length > 0 && (
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {presets.map(preset => (
            <div
              key={preset.id}
              className="group flex items-center gap-2 rounded-sheet px-2 py-1.5 hover:bg-paper-sunk"
            >
              {editingId === preset.id ? (
                <>
                  <input
                    type="text"
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={handleRenameKeyDown}
                    autoFocus
                    className="min-w-0 flex-1 rounded-sheet border border-ink bg-paper-raised px-1.5 py-0.5 text-sm focus:outline-none"
                  />
                  <button
                    onClick={handleConfirmRename}
                    aria-label={t('common:save')}
                    className="p-0.5 text-signal-ok hover:text-ink"
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                  <button
                    onClick={handleCancelRename}
                    aria-label={t('common:cancel')}
                    className="p-0.5 text-ink-muted hover:text-ink"
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </>
              ) : (
                <>
                  {/* Color swatches */}
                  <div className="flex gap-0.5">
                    {preset.colors.slice(0, 6).map((c, i) => (
                      <span
                        key={i}
                        className="h-3 w-3 border border-ink/40"
                        style={{ backgroundColor: c.hex }}
                      />
                    ))}
                    {preset.colors.length > 6 && (
                      <span className="font-mono text-[10px] text-ink-muted">+{preset.colors.length - 6}</span>
                    )}
                  </div>

                  {/* Name + load */}
                  <button
                    onClick={() => onLoadPreset(preset.colors)}
                    disabled={disabled}
                    className="flex-1 truncate text-left text-sm text-ink-soft hover:text-ink hover:underline disabled:cursor-not-allowed"
                    title={t('filaments:loadPreset', { name: preset.name, count: preset.colors.length })}
                  >
                    {preset.name}
                  </button>

                  {/* Color count */}
                  <span className="font-mono text-[10px] text-ink-muted">{t('filaments:compactCount', { count: preset.colors.length })}</span>

                  {/* Overwrite */}
                  <button
                    onClick={() => onUpdatePreset(preset.id, preset.name, currentColors)}
                    disabled={disabled || !isConfigValid}
                    className="p-0.5 text-ink-muted opacity-0 transition-opacity hover:text-ink focus-visible:opacity-100 group-hover:opacity-100 disabled:text-rule-strong"
                    title={t('filaments:overwriteWithCurrentConfig')}
                  >
                    <Save className="w-3 h-3" />
                  </button>

                  {/* Rename */}
                  <button
                    onClick={() => handleStartRename(preset)}
                    disabled={disabled}
                    className="p-0.5 text-ink-muted opacity-0 transition-opacity hover:text-ink focus-visible:opacity-100 group-hover:opacity-100 disabled:text-rule-strong"
                    title={t('filaments:rename')}
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => onDeletePreset(preset.id)}
                    disabled={disabled}
                    className="p-0.5 text-ink-muted opacity-0 transition-opacity hover:text-signal-error focus-visible:opacity-100 group-hover:opacity-100 disabled:text-rule-strong"
                    title={t('common:delete')}
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
        <p className="text-xs italic text-ink-muted">{t('filaments:noSavedPresetsYet')}</p>
      )}

      {/* Import / Export */}
      <div className="flex gap-4 border-t border-rule pt-2">
        <button
          onClick={handleExport}
          disabled={disabled || presets.length === 0}
          className="tv-link"
        >
          <Download className="h-3 w-3" aria-hidden="true" />{t('filaments:export')}</button>
        <button
          onClick={handleImportClick}
          disabled={disabled}
          className="tv-link"
        >
          <Upload className="h-3 w-3" aria-hidden="true" />{t('filaments:import')}</button>
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
        <p className={`text-xs ${importMessageType === 'success' ? 'text-signal-ok' : 'text-signal-error'}`}>
          {localize(importMessage)}
        </p>
      )}
    </div>
  );
};

export default FilamentPresetManager;
