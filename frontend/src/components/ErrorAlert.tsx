export default function ErrorAlert({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-xl border border-[var(--bad-soft)] bg-[var(--bad-soft)] px-4 py-3 text-sm">
      <div className="font-semibold text-[var(--bad)]">Something went wrong</div>
      <div className="mt-1 break-words text-[var(--bad)]">{message}</div>
    </div>
  );
}