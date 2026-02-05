import { render, screen } from '@testing-library/react';
import { StatusBadge } from './status-badge';

describe('StatusBadge', () => {
  it('renders the status text', () => {
    render(<StatusBadge status="ACTIVE" />);
    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
  });

  it('applies ACTIVE color classes (bg-success-muted text-success)', () => {
    const { container } = render(<StatusBadge status="ACTIVE" />);
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('bg-success-muted', 'text-success');
  });

  it('applies DEPRECATED color classes', () => {
    const { container } = render(<StatusBadge status="DEPRECATED" />);
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('bg-warning-muted', 'text-warning');
  });

  it('applies DRAFT color classes', () => {
    const { container } = render(<StatusBadge status="DRAFT" />);
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('bg-accent-muted', 'text-accent');
  });

  it('applies default color for unknown status', () => {
    const { container } = render(<StatusBadge status="UNKNOWN" />);
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('bg-surface-2', 'text-text-secondary');
  });

  it('has correct class structure (inline-flex, rounded-full, etc.)', () => {
    const { container } = render(<StatusBadge status="ACTIVE" />);
    const badge = container.querySelector('span');
    expect(badge).toHaveClass(
      'inline-flex',
      'items-center',
      'rounded-full',
      'px-2',
      'py-0.5',
      'text-2xs',
      'font-medium'
    );
  });
});
