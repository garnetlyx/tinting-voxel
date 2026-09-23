/**
 * Tests for ParamSearchModal component.
 * Covers config, running, results, and error phases.
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
  },
  {
    candidateId: 2,
    isBaseline: false,
    mode: 'pixel',
    params: { max_colors: 8, color_threshold: 65.19, white_backing_layers: 3 },
    previewImage: 'data:image/png;base64,def',
  },
];

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
    expect(screen.queryByText(/MAE|best/i)).not.toBeInTheDocument();
  });

  it('shows completed previews while the remaining options are still running', () => {
    render(<ParamSearchModal {...baseProps} phase="running" results={[mockResults[0]]}
      progress={{ jobId: 'job-1', completed: 1, total: 21, status: 'running', settled: false, results: [mockResults[0]] }} />);

    expect(screen.getByText('1 / 21')).toBeInTheDocument();
    expect(screen.getByAltText('Current settings')).toBeInTheDocument();
  });

  it('results step renders unranked cards and calls onApplyParams on click', async () => {
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

    // Both result cards should be visible
    expect(screen.getByText('Current settings')).toBeInTheDocument();
    expect(screen.getByText('Option 2')).toBeInTheDocument();
    expect(screen.getByText('65.19')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.queryByText('3.00')).not.toBeInTheDocument();

    // Apply the current settings card without a quality ranking.
    const firstCard = screen.getByAltText('Current settings').closest('button');
    await user.click(firstCard!);

    expect(onApplyParams).toHaveBeenCalledWith(mockResults[0].params, mockResults[0].mode, 100);
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
  });

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <ParamSearchModal {...baseProps} phase="config" isOpen={false} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
