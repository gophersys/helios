import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BackButton } from './back-button';

describe('BackButton', () => {
  it('renders label text', () => {
    const onClick = jest.fn();
    render(<BackButton label="Back to list" onClick={onClick} />);
    expect(screen.getByText('Back to list')).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const onClick = jest.fn();
    render(<BackButton label="Back" onClick={onClick} />);

    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('renders ArrowLeft icon (check for svg element)', () => {
    const onClick = jest.fn();
    const { container } = render(<BackButton label="Back" onClick={onClick} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });
});
