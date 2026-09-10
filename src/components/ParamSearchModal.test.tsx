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
};

const mockResults: SearchResultItem[] = [
  {
    rank: 1,
    mode: 'pixel',
    params: { max_colors: 10, color_threshold: 40 },
    mae: 12.5,
    previewImage: 'data:image/png;base64,abc',
  },
  {
    rank: 2,
    mode: 'pixel',
    params: { max_colors: 8, color_threshold: 60 },
    mae: 15.0,
    previewImage: 'data:image/png;base64,def',
  },
];

describe('ParamSearchModal', () => {
  it('config step renders preset selector and size input', () => {
    render(<ParamSearchModal {...baseProps} phase="config" />);

    expect(screen.getByLabelText(/target longest edge/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/filament preset/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start optimization/i })).toBeInTheDocument();
  });

  it('config step calls onStart with size and preset when confirmed', async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();

    render(<ParamSearchModal {...baseProps} phase="config" onStart={onStart} />);

    await user.click(screen.getByRole('button', { name: /start optimization/i }));

    expect(onStart).toHaveBeenCalledOnce();
    const [size, preset] = onStart.mock.calls[0];
    expect(typeof size).toBe('number');
    expect(typeof preset).toBe('string');
  });

  it('running step shows correct completed/total from progress', () => {
    const progress: ParamSearchProgress = {
      jobId: 'job-1',
      completed: 5,
      total: 20,
      bestMae: 18.3,
      status: 'running',
    };

    render(<ParamSearchModal {...baseProps} phase="running" progress={progress} />);

    expect(screen.getByText('5 / 20')).toBeInTheDocument();
    expect(screen.getByText(/18\.3/)).toBeInTheDocument();
  });

  it('results step renders top-5 cards and calls onApplyParams on click', async () => {
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
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();

    // Click the first result card (contains the rank-1 preview image)
    const firstCard = screen.getByAltText('rank 1 preview').closest('button');
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

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <ParamSearchModal {...baseProps} phase="config" isOpen={false} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
