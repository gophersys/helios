import { useLocation } from 'react-router-dom';
import { PageHeader } from '../components/ui/page-header';

export function PlaceholderPage() {
  const { pathname } = useLocation();
  const name = pathname.slice(1).replace(/-/g, ' ');
  const title = name.charAt(0).toUpperCase() + name.slice(1);

  return (
    <div className="space-y-8">
      <PageHeader
        title={title || 'Page'}
        description="This section is coming soon."
      />

      <div className="rounded-xl border border-dashed border-border bg-surface-1 p-16">
        <p className="text-center text-sm text-text-tertiary">
          {title} content will go here.
        </p>
      </div>
    </div>
  );
}
