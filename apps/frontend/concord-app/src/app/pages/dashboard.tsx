import { PageHeader } from '../components/ui/page-header';

export function DashboardPage() {
  return (
    <div className="animate-fade-in space-y-8">
      <PageHeader
        title="Dashboard"
        description="Overview of your Concord system."
      />

      <div className="rounded-xl border border-dashed border-border bg-surface-1 p-16">
        <p className="text-center text-sm text-text-tertiary">
          Dashboard content will go here.
        </p>
      </div>
    </div>
  );
}
