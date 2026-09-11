import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BugReportButton } from './BugReportButton';
import type { ConverterBugReportState } from '../api/types';
import { submitBugReport } from '../api/client';
import { captureBugReportScreenshot } from '../utils/bugReport';

vi.mock('../api/client', () => ({ submitBugReport: vi.fn() }));
vi.mock('../utils/bugReport', async importOriginal => ({
  ...await importOriginal<typeof import('../utils/bugReport')>(), captureBugReportScreenshot: vi.fn(),
}));
const context: ConverterBugReportState = {
  appMode: 'single', mode: 'pixel', pixelSize: 0.16, layerHeight: 0.08, layerCount: 4,
  whiteBackingLayers: 1, doubleSided: false, imageWidth: 1000,
  imageHeight: 1250, colorCount: 8, filamentPreset: null, processing: false, error: null,
};
const open = () => {
  render(<BugReportButton context={context} />);
  const button = screen.getByRole('button', { name: 'Report a bug' });
  button.focus(); fireEvent.click(button);
  return button;
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(submitBugReport).mockResolvedValue({ success: true, reportId: 'test-report', delivery: 'stored' });
});

describe('Bug report form', () => {
  it('opens accessibly, focuses the description, and restores focus on Escape', () => {
    const button = open();
    expect(screen.getByRole('dialog', { name: 'Report a bug' })).toBeVisible();
    expect(screen.getByRole('textbox')).toHaveFocus();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(button).toHaveFocus();
  });

  it('submits diagnostics without a screenshot by default, then closes on Done', async () => {
    open();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  Preview turned gray  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    expect(await screen.findByRole('status')).toHaveTextContent('report has been received');
    expect(submitBugReport).toHaveBeenCalledWith(expect.objectContaining({
      description: 'Preview turned gray', screenshot: undefined,
      frontendContext: expect.objectContaining({ converter: context }),
    }), expect.any(AbortSignal));
    expect(captureBugReportScreenshot).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('attaches a screenshot only when selected', async () => {
    vi.mocked(captureBugReportScreenshot).mockResolvedValue('data:image/jpeg;base64,test');
    open();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    await screen.findByRole('status');
    expect(submitBugReport).toHaveBeenCalledWith(expect.objectContaining({ screenshot: 'data:image/jpeg;base64,test' }), expect.any(AbortSignal));
  });

  it('retains the description after failure and supports retry', async () => {
    vi.mocked(submitBugReport).mockRejectedValueOnce(new Error('Service unavailable'));
    open();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Failed to download' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
    expect(screen.getByRole('textbox')).toHaveValue('Failed to download');
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    await screen.findByRole('status');
    expect(submitBugReport).toHaveBeenCalledTimes(2);
  });

  it('reports capture failures instead of silently dropping the requested screenshot', async () => {
    vi.mocked(captureBugReportScreenshot).mockRejectedValue(new Error('Canvas unavailable'));
    open();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Uncheck the screenshot option');
    expect(submitBugReport).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    await screen.findByRole('status');
  });

  it('prevents duplicate submission and dismissal while submitting', async () => {
    let finish!: (value: Awaited<ReturnType<typeof submitBugReport>>) => void;
    vi.mocked(submitBugReport).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    open();
    const send = screen.getByRole('button', { name: 'Send report' });
    fireEvent.click(send); fireEvent.click(send);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('dialog')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    expect(submitBugReport).toHaveBeenCalledTimes(1);
    await act(async () => finish({ success: true, reportId: 'confirmed', delivery: 'email' }));
    await waitFor(() => expect(screen.getByRole('status')).toBeVisible());
  });

  it('limits description length and traps keyboard navigation', () => {
    open();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'x'.repeat(1100) } });
    expect(screen.getByRole('textbox')).toHaveValue('x'.repeat(1000));
    screen.getByRole('button', { name: 'Send report' }).focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Close bug report' })).toHaveFocus();
  });
});
