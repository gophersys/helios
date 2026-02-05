import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Plus, X, Check } from 'lucide-react';
import { api } from '../../api';
import { useAuth } from '../../auth-provider';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ErrorAlert } from '../../components/ui/error-alert';
import { EmptyState } from '../../components/ui/empty-state';
import { LoadingState } from '../../components/ui/loading-state';
import { PageHeader } from '../../components/ui/page-header';
import { ProductCard } from './product-card';
import { ProductDetail } from './product-detail';
import { ApiResponse } from '../../types';
import { Product } from '../../types/models';

export function ProductsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('Concord.Admin.Products.Manage');

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formActive, setFormActive] = useState(true);

  const [submitting, setSubmitting] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  // Detail state
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  if (!hasPermission('Concord.Admin.Products.View')) {
    return <Navigate to="/" replace />;
  }

  const fetchProducts = useCallback(async () => {
    try {
      const res = await api<ApiResponse<Product[]>>('/v2/products');
      setProducts(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load products');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      const res = await api<ApiResponse<Product>>(`/v2/products/${id}`);
      setSelectedProduct(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load product');
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormActive(true);
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (p: Product) => {
    setFormName(p.name);
    setFormDescription(p.description || '');
    setFormActive(p.active);
    setEditingId(p.id);
    setShowForm(true);
    setSelectedProduct(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body = {
      name: formName,
      description: formDescription || null,
      active: formActive,
    };

    try {
      if (editingId) {
        await api(`/v2/products/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api('/v2/products', {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      fetchProducts();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save product');
    } finally {
      setSubmitting(false);
    }
  };

  const promptDelete = (id: string) => {
    const target = products.find((p) => p.id === id);
    setDeleteTarget({ id, name: target?.name || '' });
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/products/${id}`, { method: 'DELETE' });
      if (selectedProduct?.id === id) setSelectedProduct(null);
      fetchProducts();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  if (loading) {
    return (
      <div className="animate-fade-in">
        <div className="mb-6">
          <PageHeader
            title="Products"
            description="Manage products, board revisions, firmware applications, and firmware builds."
          />
        </div>
        <LoadingState message="Loading products..." />
      </div>
    );
  }

  // Detail view
  if (selectedProduct) {
    return (
      <div className="animate-fade-in">
        <div className="mb-6">
          <PageHeader
            title="Products"
            description="Manage products, board revisions, firmware applications, and firmware builds."
          />
        </div>
        <ProductDetail
          product={selectedProduct}
          canManage={canManage}
          onBack={() => setSelectedProduct(null)}
          onRefresh={() => fetchDetail(selectedProduct.id)}
        />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Products"
          description="Manage products, board revisions, firmware applications, and firmware builds."
        />
      </div>

      <ErrorAlert message={error} />

      {/* Create/Edit form */}
      {showForm && canManage && (
        <div className="mb-6 rounded-xl border border-border bg-surface-1 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              {editingId ? 'Edit product' : 'New product'}
            </h3>
            <button
              onClick={resetForm}
              className="rounded-lg p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
            >
              <X size={16} />
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="mb-3 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Name</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Sigma5"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Description</label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Optional description"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="flex items-center gap-2 text-sm text-text-primary">
                <input
                  type="checkbox"
                  checked={formActive}
                  onChange={(e) => setFormActive(e.target.checked)}
                  className="rounded border-border"
                />
                Active
              </label>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={submitting}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                <Check size={14} />
                {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Add button */}
      {canManage && !showForm && (
        <div className="mb-4 flex justify-end">
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            New product
          </button>
        </div>
      )}

      {/* Grid */}
      {products.length === 0 ? (
        <EmptyState message="No products yet" />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <ProductCard
              key={p.id}
              product={p}
              canManage={canManage}
              onEdit={startEdit}
              onDelete={promptDelete}
              onSelect={(prod) => fetchDetail(prod.id)}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="product"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
