import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ModeSelector } from './ModeSelector';

describe('ModeSelector', () => {
  it('renders pixel and vector mode buttons', () => {
    render(<ModeSelector mode="pixel" onModeChange={() => {}} />);
    expect(screen.getByText('Pixel')).toBeInTheDocument();
    expect(screen.getByText('Vector')).toBeInTheDocument();
  });

  it('marks the active mode as pressed (pixel)', () => {
    render(<ModeSelector mode="pixel" onModeChange={() => {}} />);
    expect(screen.getByText('Pixel').closest('button')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Vector').closest('button')).toHaveAttribute('aria-pressed', 'false');
  });

  it('marks the active mode as pressed (svg)', () => {
    render(<ModeSelector mode="svg" onModeChange={() => {}} />);
    expect(screen.getByText('Vector').closest('button')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Pixel').closest('button')).toHaveAttribute('aria-pressed', 'false');
  });

  it('calls onModeChange when clicking a mode button', async () => {
    const onModeChange = vi.fn();
    const user = userEvent.setup();

    render(<ModeSelector mode="pixel" onModeChange={onModeChange} />);
    await user.click(screen.getByText('Vector').closest('button')!);

    expect(onModeChange).toHaveBeenCalledWith('svg');
  });

  it('disables buttons when disabled prop is true', () => {
    render(<ModeSelector mode="pixel" onModeChange={() => {}} disabled />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach(btn => expect(btn).toBeDisabled());
  });

  it('does not call onModeChange when disabled', async () => {
    const onModeChange = vi.fn();
    const user = userEvent.setup();

    render(<ModeSelector mode="pixel" onModeChange={onModeChange} disabled />);
    await user.click(screen.getByText('Vector').closest('button')!);

    expect(onModeChange).not.toHaveBeenCalled();
  });

  it('shows descriptive text for each mode', () => {
    render(<ModeSelector mode="pixel" onModeChange={() => {}} />);
    expect(screen.getByText(/pixel art/i)).toBeInTheDocument();
    expect(screen.getByText(/logos/i)).toBeInTheDocument();
  });
});
