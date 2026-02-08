import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingSpinner } from './LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders default message when idle', () => {
    render(<LoadingSpinner />);
    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });

  it('renders custom message when provided', () => {
    render(<LoadingSpinner message="Please wait..." />);
    expect(screen.getByText('Please wait...')).toBeInTheDocument();
  });

  it('shows uploading stage label', () => {
    render(<LoadingSpinner stage="uploading" />);
    expect(screen.getByText('Uploading image...')).toBeInTheDocument();
  });

  it('shows processing stage label', () => {
    render(<LoadingSpinner stage="processing" />);
    expect(screen.getByText('Processing colors...')).toBeInTheDocument();
  });

  it('shows generating stage label', () => {
    render(<LoadingSpinner stage="generating" />);
    expect(screen.getByText('Generating STL files...')).toBeInTheDocument();
  });

  it('shows stage progress indicators when not idle', () => {
    render(<LoadingSpinner stage="processing" />);
    // Should show all three stage names (without trailing ...)
    expect(screen.getByText('Uploading image')).toBeInTheDocument();
    expect(screen.getByText('Processing colors')).toBeInTheDocument();
    expect(screen.getByText('Generating STL files')).toBeInTheDocument();
  });

  it('does not show stage indicators when idle', () => {
    render(<LoadingSpinner stage="idle" />);
    expect(screen.queryByText('Uploading image')).not.toBeInTheDocument();
  });

  it('renders a spinner animation element', () => {
    const { container } = render(<LoadingSpinner />);
    const spinner = container.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });
});
