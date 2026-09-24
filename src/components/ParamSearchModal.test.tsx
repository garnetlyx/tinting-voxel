/**
 * Tests for ParamSearchModal component.
 * Covers config, running, results, and error phases, and the ranking by score.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ParamSearchModal } from './ParamSearchModal';
import type { ParamSearchProgress, SearchResultItem } from '../api/paramSearch';

const baseProps = {
  isOpen: true,
  onClose: vi.fn(),
  onStart: vi.fn(),
  onApplyParams: vi.fn(),
  progress: null,
  results: [],
  error: null,
  imageDimensions: { width: 953, height: 1270 },
};

const mockResults: SearchResultItem[] = [
  {
    candidateId: 1,
    isBaseline: true,
    mode: 'pixel',
    params: { max_colors: 10, color_threshold: 40 },
    previewImage: 'data:image/png;base64,abc',
    score: 10.68,
  },
  {
    candidateId: 2,
    isBaseline: false,
    mode: 'pixel',
    params: { max_colors: 8, color_threshold: 65.19, white_backing_layers: 3 },
    previewImage: 'data:image/png;base64,def',
    score: 12.5,
  },
  {
    candidateId: 3,
    isBaseline: false,
    mode: 'pixel',
    params: { max_colors: 64, color_threshold: 10 },
    previewImage: 'data:image/png;base64,ghi',
    score: 8.85,
  },
];

const cardOrder = () => screen.getAllByRole('img').map((image) => image.getAttribute('alt'));

describe('ParamSearchModal', () => {
  it('config step renders size input; the search reuses the current filament config', () => {
    render(<ParamSearchModal {...baseProps} phase="config" />);

    expect(screen.getByLabelText(/target longest edge/i)).toBeInTheDocument();
    // The modal no longer carries its own preset selector: the search runs
    // against whatever the user has selected (or customized) in the main UI.
    expect(screen.queryByLabelText(/filament preset/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate options/i })).toBeInTheDocument();
  });

  it('config step calls onStart with the chosen size when confirmed', async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();

    render(<ParamSearchModal {...baseProps} phase="config" onStart={onStart} />);

    await user.click(screen.getByRole('button', { name: /generate options/i }));

    expect(onStart).toHaveBeenCalledOnce();
    const [size] = onStart.mock.calls[0];
    expect(typeof size).toBe('number');
  });

  it('running step shows correct completed/total from progress', () => {
    const progress: ParamSearchProgress = {
      jobId: 'job-1',
      completed: 5,
      total: 20,
      status: 'running',
      settled: false,
      results: [],
    };

    render(<ParamSearchModal {...baseProps} phase="running" progress={progress} />);

    expect(screen.getByText('5 / 20')).toBeInTheDocument();
    expect(screen.queryByText(/best so far|best match/i)).not.toBeInTheDocument();
  });

  it('ranks previews live while the remaining options are still running', () => {
    const { rerender } = render(<ParamSearchModal {...baseProps} phase="running" results={mockResults.slice(0, 2)}
      progress={{ jobId: 'job-1', completed: 2, total: 21, status: 'running', settled: false, results: [] }} />);

    expect(screen.getByText('2 / 21')).toBeInTheDocument();
    expect(cardOrder()).toEqual(['Current settings', 'Option 2']);
    expect(screen.getByText('Best so far')).toBeInTheDocument();
    expect(screen.queryByText('Best match')).not.toBeInTheDocument();

    rerender(<ParamSearchModal {...baseProps} phase="running" results={mockResults}
      progress={{ jobId: 'job-1', completed: 3, total: 21, status: 'running', settled: false, results: [] }} />);
    expect(cardOrder()).toEqual(['Option 3', 'Current settings', 'Option 2']);
  });

  it('results step ranks cards by color difference and applies the selected one', async () => {
    const user = userEvent.setup();
    const onApplyParams = vi.fn();
    const onClose = vi.fn();

    render(
      <ParamSearchModal
        {...baseProps}
        phase="results"
        results={mockResults}
        onApplyParams={onApplyParams}
        onClose={onClose}
      />,
    );

    expect(cardOrder()).toEqual(['Option 3', 'Current settings', 'Option 2']);
    expect(screen.getByText('Best match')).toBeInTheDocument();
    expect(screen.getByText('ΔE 8.85')).toBeInTheDocument();
    expect(screen.getByText('ΔE 10.68')).toBeInTheDocument();
    expect(screen.getByText('1.83 closer than current')).toBeInTheDocument();
    expect(screen.getByText('1.82 further than current')).toBeInTheDocument();
    expect(screen.getByText('65.19')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.queryByText('3.00')).not.toBeInTheDocument();

    await user.click(screen.getByAltText('Option 3').closest('button')!);

    expect(onApplyParams).toHaveBeenCalledWith(mockResults[2].params, mockResults[2].mode, 100);
    expect(onClose).toHaveBeenCalled();
  });

  it('error state shows error message with retry and close buttons', () => {
    render(
      <ParamSearchModal
        {...baseProps}
        phase="error"
        error="Network timeout"
      />,
    );

    expect(screen.getByText('Network timeout')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    // Two "Close" buttons exist: the header ✕ (aria-label) and the body close button
    expect(screen.getAllByRole('button', { name: /close/i })).toHaveLength(2);
  });

  it('keeps completed previews available if a later candidate fails', () => {
    render(<ParamSearchModal {...baseProps} phase="error" error="Candidate failed" results={[mockResults[0]]} />);
    expect(screen.getByText('Candidate failed')).toBeInTheDocument();
    expect(screen.getByAltText('Current settings')).toBeInTheDocument();
    expect(screen.getByText('Best so far')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <ParamSearchModal {...baseProps} phase="config" isOpen={false} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
