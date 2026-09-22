import { cn } from "@/lib/utils";

/**
 * Cascade mark — three descending blades stepping down a slope: a cascade
 * of flow, a blade row. Drawn as an app icon: inverse strokes on a solid
 * brand tile.
 */
export function CascadeMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[6px] bg-brand shadow-z1",
        className,
      )}
    >
      <svg
        viewBox="0 0 16 16"
        fill="none"
        className="h-3.5 w-3.5 text-text-inverse"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
      >
        {/* Three stepping blades — the cascade. */}
        <path d="M3 4.5h7" />
        <path d="M4.5 8h7" opacity="0.8" />
        <path d="M6 11.5h7" opacity="0.6" />
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
      <span className="text-sm font-semibold tracking-tight text-text">
        Cascade
      </span>
    </div>
  );
}
