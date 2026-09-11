import { afterEach, describe, expect, it, vi } from 'vitest';
import { captureBugReportScreenshot, collectBugReportContext, initializeBugReportDiagnostics, recordBugReportLog, sanitizeDiagnostic } from './bugReport';
import type { ConverterBugReportState } from '../api/types';
import html2canvas from 'html2canvas';

vi.mock('html2canvas', () => ({ default: vi.fn() }));
const context: ConverterBugReportState = {
  appMode: 'batch', mode: 'svg', pixelSize: 0.16, layerHeight: 0.08, layerCount: 4,
  whiteBackingLayers: 1, imageWidth: 1000,
  imageHeight: 1250, colorCount: 8, filamentPreset: null, processing: false, error: null,
};
afterEach(() => { vi.restoreAllMocks(); window.history.replaceState({}, '', '/'); });

describe('Bug report diagnostics', () => {
  it('includes conversion settings and excludes URL query/hash and storage', () => {
    window.history.replaceState({}, '', '/?token=private#secret');
    localStorage.setItem('token', 'private-storage');
    const report = collectBugReportContext(context);
    expect(report.url).not.toContain('token');
    expect(JSON.stringify(report)).not.toContain('private');
    expect(report.converter).toEqual(context);
    expect(report.viewport.width).toBeGreaterThan(0);
  });

  it('bounds diagnostic history and returns independent entries', () => {
    for (let i = 0; i < 110; i++) recordBugReportLog('error', `failure ${i}`);
    const report = collectBugReportContext(context);
    expect(report.debugLogs).toHaveLength(100);
    expect(report.debugLogs[0].message).toBe('failure 10');
    report.debugLogs[0].message = 'changed';
    expect(collectBugReportContext(context).debugLogs[0].message).toBe('failure 10');
  });

  it('captures browser errors and removes its listeners on cleanup', () => {
    const cleanup = initializeBugReportDiagnostics();
    window.dispatchEvent(new ErrorEvent('error', { message: 'WebGL failed' }));
    expect(collectBugReportContext(context).debugLogs.slice(-1)[0]?.message).toBe('WebGL failed');
    cleanup();
    window.dispatchEvent(new ErrorEvent('error', { message: 'After cleanup' }));
    expect(collectBugReportContext(context).debugLogs.slice(-1)[0]?.message).toBe('WebGL failed');
  });

  it('redacts common secrets and image payloads', () => {
    const sanitized = sanitizeDiagnostic('token=abc password=xyz Bearer abc123 https://test.local/path?token=abcdef data:image/png;base64,huge');
    for (const secret of ['abc123', 'abcdef', 'xyz', 'base64,huge']) expect(sanitized).not.toContain(secret);
    expect(sanitizeDiagnostic('x'.repeat(3000))).toHaveLength(1000);
    expect(sanitizeDiagnostic('Authorization: Bearer secret-token')).not.toContain('secret-token');
    expect(sanitizeDiagnostic('{"password": "private value"}')).not.toContain('private value');
  });
});

describe('Bug report screenshot', () => {
  it('captures the selected language label without changing the live selection', async () => {
    document.body.innerHTML = '<div id="root"><select><option value="en">English</option><option value="zh-CN">简体中文</option></select></div>';
    const select = document.querySelector('select')!;
    select.value = 'zh-CN';
    vi.spyOn(select, 'getBoundingClientRect').mockReturnValue({ width: 84, height: 20 } as DOMRect);
    vi.mocked(html2canvas).mockImplementation(async (_target, options) => {
      const clone = document.implementation.createHTMLDocument();
      clone.body.innerHTML = document.body.innerHTML;
      await options!.onclone!(clone, clone.body);
      expect(clone.querySelector('select')).toBeNull();
      const label = clone.querySelector('#root span') as HTMLElement;
      expect(label.textContent).toBe('简体中文');
      expect(label.style.width).toBe('84px');
      expect(label.style.height).toBe('20px');
      return { toDataURL: () => 'data:image/jpeg;base64,small' } as HTMLCanvasElement;
    });
    await captureBugReportScreenshot();
    expect(select.isConnected).toBe(true);
    expect(select.value).toBe('zh-CN');
    document.body.innerHTML = '';
  });

  it('preserves slider positions in the screenshot without changing live controls', async () => {
    document.body.innerHTML = '<div id="root"><input type="range" min="10" max="20" value="15"><input type="range" value="100"><input type="password" value="private"></div>';
    document.querySelectorAll('input[type="range"]').forEach(input => {
      vi.spyOn(input, 'getBoundingClientRect').mockReturnValue({ width: 116, height: 16 } as DOMRect);
    });
    vi.mocked(html2canvas).mockImplementation(async (_target, options) => {
      const clone = document.implementation.createHTMLDocument();
      clone.body.innerHTML = document.body.innerHTML;
      await options!.onclone!(clone, clone.body);
      expect(clone.querySelector('input[type="range"]')).toBeNull();
      const controls = clone.querySelector('#root')!.children;
      expect((controls[0].lastElementChild as HTMLElement).style.left).toBe('50px');
      expect((controls[1].lastElementChild as HTMLElement).style.left).toBe('100px');
      expect(clone.querySelector<HTMLInputElement>('input[type="password"]')!.value).toBe('');
      return { toDataURL: () => 'data:image/jpeg;base64,small' } as HTMLCanvasElement;
    });
    await captureBugReportScreenshot();
    expect(document.querySelectorAll('input[type="range"]')).toHaveLength(2);
    expect(document.querySelector<HTMLInputElement>('input[type="password"]')!.value).toBe('private');
    document.body.innerHTML = '';
  });

  it('uses a viewport crop and refreshes WebGL before capturing canvas images', async () => {
    document.body.innerHTML = '<div id="root"><canvas></canvas></div>';
    const screenshot = 'data:image/jpeg;base64,small';
    const captureEvent = vi.fn();
    document.addEventListener('tinting-voxel:capture-report', captureEvent);
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockImplementation(() => {
      expect(captureEvent).toHaveBeenCalled();
      return 'data:image/png;base64,canvas';
    });
    vi.mocked(html2canvas).mockResolvedValue({ toDataURL: () => screenshot } as HTMLCanvasElement);
    expect(await captureBugReportScreenshot()).toBe(screenshot);
    expect(html2canvas).toHaveBeenCalledWith(document.getElementById('root'), expect.objectContaining({ width: window.innerWidth, height: window.innerHeight, logging: false }));
    document.removeEventListener('tinting-voxel:capture-report', captureEvent);
    document.body.innerHTML = '';
  });
});
