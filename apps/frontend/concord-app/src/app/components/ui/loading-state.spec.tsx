import { render, screen } from '@testing-library/react';
import { LoadingState } from './loading-state';

describe('LoadingState', () => {
  it('renders the message text', () => {
    render(<LoadingState message="Loading data..." />);
    expect(screen.getByText('Loading data...')).toBeInTheDocument();
  });
});
