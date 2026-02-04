export function EmptyState({ message }: { message: string }) {
  return (
    <div className="py-12 text-center text-sm text-text-tertiary">
      {message}
    </div>
  );
}
