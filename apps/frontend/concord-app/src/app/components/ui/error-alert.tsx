export function ErrorAlert({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="mb-4 rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
      {message}
    </div>
  );
}
