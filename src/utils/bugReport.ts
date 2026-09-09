import { i18n } from '../i18n';
import type { BugReportContext, BugReportLog, ConverterBugReportState } from '../api/types';

export const BUG_REPORT_CAPTURE_EVENT = 'tinting-voxel:capture-report';
const logs: BugReportLog[] = [];
let initialized = false;

/** Keep diagnostics small and avoid retaining credentials or image payloads. */
export function sanitizeDiagnostic(message: string): string {
  return message
    .replace(/data:[^\s]+/gi, '[image data]')
    .replace(/https?:\/\/[^\s)]+/gi, value => {
      try { const url = new URL(value); return `${url.origin}${url.pathname}`; } catch { return '[URL]'; }
    })
    .replace(/Bearer\s+\S+/gi, 'Bearer [redacted]')
    .replace(/(authorization|api[_-]?key|token|password|secret)["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;]+)/gi, '$1=[redacted]')
    .slice(0, 1000);
}

export function recordBugReportLog(level: BugReportLog['level'], message: string): void {
  logs.push({ level, message: sanitizeDiagnostic(message), timestamp: new Date().toISOString() });
  if (logs.length > 100) logs.shift();
}

export function initializeBugReportDiagnostics(): () => void {
  if (initialized) return () => {};
  initialized = true;
  const onError = (event: ErrorEvent) => recordBugReportLog('error', event.message || 'Page resource failed to load');
  const onRejection = (event: PromiseRejectionEvent) => recordBugReportLog(
    'error', event.reason instanceof Error ? event.reason.message : String(event.reason),
  );
  window.addEventListener('error', onError);
  window.addEventListener('unhandledrejection', onRejection);
  return () => {
    initialized = false;
    window.removeEventListener('error', onError);
    window.removeEventListener('unhandledrejection', onRejection);
  };
}

export function collectBugReportContext(converter: ConverterBugReportState): BugReportContext {
  return {
    url: `${window.location.origin}${window.location.pathname}`.slice(0, 2000),
    userAgent: navigator.userAgent.slice(0, 500),
    language: (i18n.resolvedLanguage ?? navigator.language).slice(0, 40),
    timestamp: new Date().toISOString(),
    viewport: { width: window.innerWidth, height: window.innerHeight },
    converter: { ...converter, error: converter.error ? sanitizeDiagnostic(converter.error) : null },
    debugLogs: logs.map(entry => ({ ...entry })),
  };
}

/** Capture the visible page, excluding report UI and preserving WebGL previews. */
export async function captureBugReportScreenshot(): Promise<string> {
  const { default: html2canvas } = await import('html2canvas');
  const target = document.getElementById('root') ?? document.body;
  // Read WebGL canvases synchronously after their renderers refresh the frame.
  document.dispatchEvent(new Event(BUG_REPORT_CAPTURE_EVENT));
  const snapshots = Array.from(target.querySelectorAll('canvas')).map(canvas => canvas.toDataURL('image/png'));
  // Native range controls are rendered as clipped text by html2canvas.
  const ranges = Array.from(target.querySelectorAll<HTMLInputElement>('input[type="range"]')).map(input => {
    const bounds = input.getBoundingClientRect();
    const style = getComputedStyle(input);
    const min = input.min === '' ? 0 : Number(input.min);
    const max = input.max === '' ? 100 : Number(input.max);
    return {
      width: bounds.width, height: bounds.height,
      fraction: max > min ? Math.max(0, Math.min(1, (input.valueAsNumber - min) / (max - min))) : 0,
      color: style.accentColor === 'auto' ? '#2563eb' : style.accentColor,
      direction: style.direction,
    };
  });
  // Snapshot native select labels before cloning; html2canvas clips their text baseline.
  const selects = Array.from(target.querySelectorAll('select')).map(select => {
    const bounds = select.getBoundingClientRect();
    return { width: bounds.width, height: bounds.height, text: select.selectedOptions[0]?.text ?? '' };
  });
  const canvas = await html2canvas(target, {
    logging: false,
    useCORS: true,
    scale: Math.min(1, 1440 / window.innerWidth),
    x: window.scrollX,
    y: window.scrollY,
    width: window.innerWidth,
    height: window.innerHeight,
    onclone: documentClone => {
      const clonedTarget = documentClone.getElementById('root') ?? documentClone.body;
      clonedTarget.querySelectorAll('canvas').forEach((clonedCanvas, index) => {
        const image = documentClone.createElement('img');
        image.src = snapshots[index];
        image.width = clonedCanvas.width;
        image.height = clonedCanvas.height;
        image.className = clonedCanvas.className;
        image.style.cssText = clonedCanvas.style.cssText;
        clonedCanvas.replaceWith(image);
      });
      clonedTarget.querySelectorAll<HTMLInputElement>('input[type="range"]').forEach((input, index) => {
        const range = ranges[index];
        const control = documentClone.createElement('span');
        control.className = input.className;
        control.style.cssText = input.style.cssText;
        Object.assign(control.style, {
          display: 'inline-block', position: 'relative', boxSizing: 'border-box',
          width: `${range.width}px`, height: `${range.height}px`,
          opacity: input.disabled ? '0.5' : '1',
        });
        const thumbSize = Math.min(16, range.height, range.width);
        const offset = (range.width - thumbSize) * range.fraction;
        const track = documentClone.createElement('span');
        Object.assign(track.style, {
          position: 'absolute', left: `${thumbSize / 2}px`, right: `${thumbSize / 2}px`,
          top: `${(range.height - 4) / 2}px`, height: '4px',
          borderRadius: '2px', backgroundColor: '#d1d5db',
        });
        const fill = documentClone.createElement('span');
        Object.assign(fill.style, {
          position: 'absolute', [range.direction === 'rtl' ? 'right' : 'left']: '0',
          top: '0', height: '4px', width: `${range.fraction * 100}%`,
          backgroundColor: range.color, borderRadius: '2px',
        });
        const thumb = documentClone.createElement('span');
        Object.assign(thumb.style, {
          position: 'absolute', [range.direction === 'rtl' ? 'right' : 'left']: `${offset}px`,
          top: `${(range.height - thumbSize) / 2}px`,
          width: `${thumbSize}px`, height: `${thumbSize}px`,
          borderRadius: '50%', backgroundColor: range.color,
        });
        track.append(fill);
        control.append(track, thumb);
        input.replaceWith(control);
      });
      clonedTarget.querySelectorAll('select').forEach((select, index) => {
        const snapshot = selects[index];
        const label = documentClone.createElement('span');
        label.className = select.className;
        label.style.cssText = select.style.cssText;
        Object.assign(label.style, {
          display: 'inline-flex', alignItems: 'center', boxSizing: 'border-box',
          width: `${snapshot.width}px`, height: `${snapshot.height}px`,
          whiteSpace: 'nowrap', overflow: 'visible',
        });
        label.textContent = snapshot.text;
        select.replaceWith(label);
      });
      clonedTarget.querySelectorAll<HTMLInputElement>('input[type="password"]').forEach(input => { input.value = ''; });
    },
  });
  for (const quality of [0.7, 0.4]) {
    const dataUrl = canvas.toDataURL('image/jpeg', quality);
    if (dataUrl.startsWith('data:image/jpeg;base64,') && dataUrl.length <= 4 * 1024 * 1024) return dataUrl;
  }
  throw new Error('Screenshot is too large');
}
