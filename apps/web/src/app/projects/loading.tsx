export default function Loading() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="flex items-center gap-2 text-sm text-text-muted">
        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-brand border-t-transparent" />
        Loading projects…
      </div>
    </div>
  );
}
