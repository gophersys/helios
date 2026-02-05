export function ResourceAge({ timestamp }: { timestamp: string | null }) {
  if (!timestamp) return <span className="text-text-tertiary">-</span>;

  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  let display: string;
  if (diffMins < 1) display = '<1m';
  else if (diffMins < 60) display = `${diffMins}m`;
  else if (diffHours < 24) display = `${diffHours}h`;
  else display = `${diffDays}d`;

  return (
    <span className="text-text-secondary" title={date.toLocaleString()}>
      {display}
    </span>
  );
}
