import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from '../../../testing/render-app';
import { createProduct } from '../../../testing/fixtures';
import { ProductCard } from './product-card';

describe('ProductCard', () => {
  const defaultProps = {
    product: createProduct(),
    canManage: false,
    onEdit: jest.fn(),
    onDelete: jest.fn(),
    onSelect: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders product name', () => {
    renderApp(<ProductCard {...defaultProps} />);
    expect(screen.getByText('Sigma5')).toBeInTheDocument();
  });

  it('renders description if provided', () => {
    const product = createProduct({ description: 'Test description' });
    renderApp(<ProductCard {...defaultProps} product={product} />);
    expect(screen.getByText('Test description')).toBeInTheDocument();
  });

  it('shows "Active" status when product.active is true', () => {
    const product = createProduct({ active: true });
    renderApp(<ProductCard {...defaultProps} product={product} />);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('shows "Inactive" status when product.active is false', () => {
    const product = createProduct({ active: false });
    renderApp(<ProductCard {...defaultProps} product={product} />);
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('shows board revision, firmware app, and build counts', () => {
    const product = createProduct({
      boardRevisionCount: 3,
      firmwareAppCount: 2,
      firmwareBuildCount: 10,
    });
    renderApp(<ProductCard {...defaultProps} product={product} />);
    expect(screen.getByText(/3 board revs/)).toBeInTheDocument();
    expect(screen.getByText(/2 fw apps/)).toBeInTheDocument();
    expect(screen.getByText(/10 builds/)).toBeInTheDocument();
  });

  it('calls onSelect when card is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    const product = createProduct();
    renderApp(
      <ProductCard {...defaultProps} product={product} onSelect={onSelect} />
    );

    const card = screen.getByText('Sigma5').closest('div');
    await user.click(card!);

    expect(onSelect).toHaveBeenCalledWith(product);
  });

  it('shows edit/delete buttons when canManage is true', () => {
    renderApp(<ProductCard {...defaultProps} canManage={true} />);
    expect(screen.getByTitle('Edit')).toBeInTheDocument();
    expect(screen.getByTitle('Delete')).toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', async () => {
    const user = userEvent.setup();
    const onEdit = jest.fn();
    const product = createProduct();
    renderApp(
      <ProductCard {...defaultProps} product={product} canManage={true} onEdit={onEdit} />
    );

    await user.click(screen.getByTitle('Edit'));

    expect(onEdit).toHaveBeenCalledWith(product);
  });

  it('calls onDelete when delete button is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();
    const product = createProduct({ id: 'test-id' });
    renderApp(
      <ProductCard {...defaultProps} product={product} canManage={true} onDelete={onDelete} />
    );

    await user.click(screen.getByTitle('Delete'));

    expect(onDelete).toHaveBeenCalledWith('test-id');
  });

  it('does not show edit/delete buttons when canManage is false', () => {
    renderApp(<ProductCard {...defaultProps} canManage={false} />);
    expect(screen.queryByTitle('Edit')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Delete')).not.toBeInTheDocument();
  });
});
