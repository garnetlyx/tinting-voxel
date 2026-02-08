import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DownloadButtons } from './DownloadButtons';

describe('DownloadButtons', () => {
  const defaultProps = {
    colorCount: 5,
    onDownloadCSV: vi.fn(),
    onDownloadSTL: vi.fn(),
    processing: false,
  };

  it('displays extracted color count', () => {
    render(<DownloadButtons {...defaultProps} />);
    expect(screen.getByText('Extracted Colors (5)')).toBeInTheDocument();
  });

  it('shows CSV button by default', () => {
    render(<DownloadButtons {...defaultProps} />);
    expect(screen.getByText('Download CSV')).toBeInTheDocument();
  });

  it('hides CSV button when showCSV is false', () => {
    render(<DownloadButtons {...defaultProps} showCSV={false} />);
    expect(screen.queryByText('Download CSV')).not.toBeInTheDocument();
  });

  it('shows STL download button', () => {
    render(<DownloadButtons {...defaultProps} />);
    expect(screen.getByText('Download STL (ZIP)')).toBeInTheDocument();
  });

  it('shows "Generating..." text when processing', () => {
    render(<DownloadButtons {...defaultProps} processing />);
    expect(screen.getByText('Generating...')).toBeInTheDocument();
    expect(screen.queryByText('Download STL (ZIP)')).not.toBeInTheDocument();
  });

  it('disables all buttons when processing', () => {
    render(
      <DownloadButtons
        {...defaultProps}
        processing
        onDownload3MF={vi.fn()}
        onDownloadPrintSettings={vi.fn()}
      />
    );
    const buttons = screen.getAllByRole('button');
    buttons.forEach(btn => expect(btn).toBeDisabled());
  });

  it('calls onDownloadCSV when CSV button clicked', async () => {
    const onDownloadCSV = vi.fn();
    const user = userEvent.setup();

    render(<DownloadButtons {...defaultProps} onDownloadCSV={onDownloadCSV} />);
    await user.click(screen.getByText('Download CSV'));

    expect(onDownloadCSV).toHaveBeenCalledOnce();
  });

  it('calls onDownloadSTL when STL button clicked', async () => {
    const onDownloadSTL = vi.fn();
    const user = userEvent.setup();

    render(<DownloadButtons {...defaultProps} onDownloadSTL={onDownloadSTL} />);
    await user.click(screen.getByText('Download STL (ZIP)'));

    expect(onDownloadSTL).toHaveBeenCalledOnce();
  });

  it('shows 3MF button when handler provided', () => {
    render(<DownloadButtons {...defaultProps} onDownload3MF={vi.fn()} />);
    expect(screen.getByText('Download 3MF')).toBeInTheDocument();
  });

  it('does not show 3MF button when handler not provided', () => {
    render(<DownloadButtons {...defaultProps} />);
    expect(screen.queryByText('Download 3MF')).not.toBeInTheDocument();
  });

  it('shows print settings button when handler provided', () => {
    render(<DownloadButtons {...defaultProps} onDownloadPrintSettings={vi.fn()} />);
    expect(screen.getByText('Print Settings')).toBeInTheDocument();
  });

  it('calls onDownload3MF when 3MF button clicked', async () => {
    const onDownload3MF = vi.fn();
    const user = userEvent.setup();

    render(<DownloadButtons {...defaultProps} onDownload3MF={onDownload3MF} />);
    await user.click(screen.getByText('Download 3MF'));

    expect(onDownload3MF).toHaveBeenCalledOnce();
  });

  it('calls onDownloadPrintSettings when print settings button clicked', async () => {
    const onDownloadPrintSettings = vi.fn();
    const user = userEvent.setup();

    render(<DownloadButtons {...defaultProps} onDownloadPrintSettings={onDownloadPrintSettings} />);
    await user.click(screen.getByText('Print Settings'));

    expect(onDownloadPrintSettings).toHaveBeenCalledOnce();
  });
});
