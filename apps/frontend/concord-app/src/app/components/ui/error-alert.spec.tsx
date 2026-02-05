import { render, screen } from '@testing-library/react';
import { ErrorAlert } from './error-alert';

describe('ErrorAlert', () => {
  it('renders error message when provided', () => {
    render(<ErrorAlert message="Something went wrong" />);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('returns null (renders nothing) when message is null', () => {
    const { container } = render(<ErrorAlert message={null} />);
    expect(container.firstChild).toBeNull();
  });
});
