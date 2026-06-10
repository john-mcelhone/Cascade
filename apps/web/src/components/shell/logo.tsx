import { cn } from "@/lib/utils";

/**
 * Cascade mark — three descending blades stepping down a slope inside a
 * machined square frame: a cascade of flow, a blade row, an instrument
 * faceplate. Flat brand cyan on the panel surface; no gradients.
 */
export function CascadeMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex h-5 w-5 items-center justify-center rounded-sm border border-brand/60 bg-brand-surface",
        className,
      )}
    >
      <svg
        viewBox="0 0 16 16"
        fill="none"
        className="h-3.5 w-3.5 text-brand"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="square"
      >
        {/* Three stepping blades — the cascade. */}
        <path d="M3 4.5h7" opacity="0.95" />
        <path d="M4.5 8h7" opacity="0.75" />
        <path d="M6 11.5h7" opacity="0.55" />
      </svg>
    </span>
  );
}

export function Logo({
  className,
  showMark = true,
}: {
  className?: string;
  showMark?: boolean;
}) {
  return (
    <div
      className={cn("inline-flex items-center gap-2 select-none", className)}
    >
      {showMark && <CascadeMark />}
      <span className="text-sm font-semibold uppercase tracking-caps text-text">
        Cascade
      </span>
    </div>
  );
}
