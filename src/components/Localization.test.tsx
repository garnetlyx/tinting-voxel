import { useState } from 'react';
import { act, cleanup, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { i18n, initializeLocale, setLocale, useTranslation } from '../i18n';
import { usePaletteText, usePresetLabel } from '../i18n/catalog';
import { useImageProcessor } from '../hooks/useImageProcessor';
import { FilamentConfigPanel } from './FilamentConfigPanel';
import { ErrorMessage } from './ErrorMessage';
import { LanguageSelector } from './LanguageSelector';
import { BugReportModal } from './BugReportModal';
import { FilamentPreview } from './FilamentPreview';
import * as api from '../api/client';
import type { FilamentColorConfig } from '../api/types';

const colors: FilamentColorConfig[] = 'QRSTUV'.split('').map((code, index) => ({
  name: `${code}-custom material`, hex: `#${(0x345678 + index * 0x101010).toString(16)}`, transmission_distance: 1.1 + index,
}));

beforeEach(() => { localStorage.clear(); setLocale('en'); initializeLocale(); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); setLocale('en'); localStorage.clear(); });

describe('live localization boundaries', () => {
  it('keeps dynamic color data and input nodes unchanged when switching language', async () => {
    const onUpdate = vi.fn();
    const user = userEvent.setup();
    function Workspace() {
      const [entries, setEntries] = useState(colors);
      return <><LanguageSelector /><FilamentConfigPanel filamentPreset={null} filamentColors={entries} isValid
        onLoadPreset={vi.fn()} onAddColor={vi.fn()} onRemoveColor={vi.fn()}
        onUpdateColor={(index, entry) => { onUpdate(index, entry); setEntries(previous => previous.map((color, i) => i === index ? entry : color)); }}
      /><output data-testid="data">{JSON.stringify(entries)}</output></>;
    }
    render(<Workspace />);
    const input = screen.getByRole('textbox', { name: /Color 1 · Q/ });
    expect(input).toHaveValue('Q');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Language' }), 'zh-CN');
    expect(screen.getByRole('textbox', { name: /颜色 1 · Q/ })).toBe(input);
    expect(screen.getByText('6 / 16 种颜色')).toBeInTheDocument();
    expect(screen.getByTestId('data').textContent).toBe(JSON.stringify(colors));
    expect(onUpdate).not.toHaveBeenCalled();
    await user.clear(input);
    await user.type(input, 'z');
    expect(input).toHaveValue('Z');
    expect(onUpdate).toHaveBeenLastCalledWith(0, { ...colors[0], name: 'Z' });
    expect(JSON.parse(screen.getByTestId('data').textContent!)[1]).toEqual(colors[1]);
    await user.selectOptions(screen.getByRole('combobox', { name: '语言' }), 'en');
    expect(input).toHaveValue('Z');
  });

  it('retains actual converter parameters, custom colors and existing errors across a language change', async () => {
    const { result } = renderHook(() => ({ processor: useImageProcessor(), locale: useTranslation().i18n.resolvedLanguage }));
    act(() => {
      result.current.processor.loadSavedPresetColors(colors);
      result.current.processor.setMaxColors(17);
      result.current.processor.setPixelSize(0.65);
      result.current.processor.handleFile(new File(['invalid'], 'unsupported.avif', { type: 'image/avif' }));
    });
    const previousColors = result.current.processor.filamentColors;
    const previousError = result.current.processor.error;
    act(() => setLocale('zh-CN'));
    expect(result.current.locale).toBe('zh-CN');
    expect(result.current.processor.filamentColors).toBe(previousColors);
    expect(result.current.processor.filamentColors).toEqual(colors);
    expect(result.current.processor.maxColors).toBe(17);
    expect(result.current.processor.pixelSize).toBe(0.65);
    expect(result.current.processor.error).toBe(previousError);
    expect(result.current.processor.processing).toBe(false);
  });

  it('retranslates an already displayed error without changing its canonical text', () => {
    const error = 'Failed to download STL';
    render(<ErrorMessage message={error} />);
    expect(screen.getByText(error)).toBeInTheDocument();
    act(() => setLocale('zh-CN'));
    expect(screen.getByText('STL 下载失败')).toBeInTheDocument();
  });

  it('retains a feedback draft and screenshot choice while changing language', async () => {
    const user = userEvent.setup();
    render(<BugReportModal onClose={vi.fn()} context={{ appMode: 'single', mode: 'pixel', pixelSize: 0.16, layerHeight: 0.08, layerCount: 4, whiteBackingLayers: 1, basePlateThickness: 0, doubleSided: false, imageWidth: 1000, imageHeight: 1250, colorCount: 8, filamentPreset: null, processing: false, error: null }} />);
    const description = screen.getByRole('textbox');
    await user.type(description, '我的自定义材料 Q has an issue');
    await user.click(screen.getByRole('checkbox'));
    act(() => setLocale('zh-CN'));
    expect(description).toHaveValue('我的自定义材料 Q has an issue');
    expect(screen.getByRole('checkbox')).toBeChecked();
    expect(screen.getByRole('button', { name: '发送反馈' })).toBeInTheDocument();
  });

  it('uses catalog IDs for known metadata and preserves unknown entries', () => {
    const { result } = renderHook(() => ({ preset: usePresetLabel(), palette: usePaletteText() }));
    act(() => setLocale('zh-CN'));
    expect(result.current.preset('bambu_cmyw_phase6', 'fallback')).toContain('第六阶段');
    expect(result.current.preset('new-dynamic-preset', 'My custom 8-color palette')).toBe('My custom 8-color palette');
    expect(result.current.palette('new-palette_name', '新配色 Q')).toBe('新配色 Q');
  });

  it('does not request a new filament preview when switching language', async () => {
    vi.useFakeTimers();
    const preview = vi.spyOn(api, 'getFilamentPreview').mockResolvedValue({
      image: '', colorMatrix: [], stats: { colorCount: colors.length, combinationCount: 1296 },
      imageDimensions: { width: 1, height: 1 }, warnings: [],
    });
    render(<FilamentPreview filamentColors={colors} filamentPreset={null} layerCount={4} layerHeight={0.08} isConfigValid />);
    await act(() => vi.advanceTimersByTimeAsync(550));
    expect(preview).toHaveBeenCalledOnce();
    expect(preview.mock.calls[0][0]).toEqual({ filamentColors: colors, layerCount: 4, layerHeight: 0.08 });
    act(() => setLocale('zh-CN'));
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(preview).toHaveBeenCalledOnce();
    expect(screen.getByText('6 种耗材颜色')).toBeInTheDocument();
    expect(i18n.resolvedLanguage).toBe('zh-CN');
  });
});
